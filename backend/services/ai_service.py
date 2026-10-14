"""
AIService — provider-agnostic interface for narrative generation.

Provider modes (set via AI_PROVIDER in .env):
  "demo"   — rule-based, answers from analytics data. No API key needed.
  "gemini" — Google Gemini via REST (AI_BASE_URL + AI_MODEL_NAME + AI_API_KEY)
  "openai" — OpenAI-compatible endpoint (AI_BASE_URL + AI_MODEL_NAME + AI_API_KEY)
  "custom" — Any OpenAI-compatible API (AI_BASE_URL + AI_MODEL_NAME + AI_API_KEY)

IMPORTANT: Only aggregated numbers are ever sent to external providers.
           Never send raw opportunity rows or PII.
"""
from __future__ import annotations

import json
import logging
from datetime import date
from typing import Protocol

import httpx
from sqlalchemy.orm import Session

from backend.config import settings
from backend.services.context import UserContext
from backend.services.analytics_service import AnalyticsService

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Provider protocol
# ---------------------------------------------------------------------------

class AIProvider(Protocol):
    def chat(self, system_prompt: str, user_message: str) -> str: ...


# ---------------------------------------------------------------------------
# Demo / rule-based provider
# ---------------------------------------------------------------------------

class DemoProvider:
    """Answers queries from analytics data without any external API call."""

    def __init__(self, analytics: AnalyticsService, ctx: UserContext):
        self.analytics = analytics
        self.ctx = ctx

    def chat(self, system_prompt: str, user_message: str) -> str:
        kpis = self.analytics.get_kpis(self.ctx)
        forecast = self.analytics.get_approval_status(self.ctx)
        msg_lower = user_message.lower()

        if any(w in msg_lower for w in ["total", "acv", "pipeline", "value"]):
            total = kpis.get("total_acv", 0)
            return (
                f"The current total pipeline ACV is **${total/1_000_000:.2f}M** "
                f"across **{kpis.get('total_count', 0):,}** opportunities. "
                f"Commit ACV is **${kpis.get('commit_acv', 0)/1_000_000:.2f}M** "
                f"and Closed ACV is **${kpis.get('closed_acv', 0)/1_000_000:.2f}M**."
            )

        if any(w in msg_lower for w in ["approval", "approved", "pending", "rejected"]):
            rows = forecast.get("rows", [])
            parts = [f"**{r['approval_status']}**: {r['count']:,} opps (${r['acv']/1_000_000:.2f}M)" for r in rows]
            return "Approval status breakdown:\n" + "\n".join(f"- {p}" for p in parts)

        return (
            "I'm in demo mode and can answer questions about pipeline totals, "
            "forecast categories, approval status, and regional breakdowns. "
            "Try asking: *'What is the total ACV?'* or *'Show approval status breakdown'*."
        )


# ---------------------------------------------------------------------------
# External REST provider (Gemini / OpenAI-compatible)
# ---------------------------------------------------------------------------

class ExternalProvider:
    def __init__(self):
        self.base_url = settings.AI_BASE_URL.rstrip("/")
        self.model = settings.AI_MODEL_NAME
        self.api_key = settings.AI_API_KEY

    def chat(self, system_prompt: str, user_message: str) -> str:
        # OpenAI-compatible format (works for Gemini with /v1/chat/completions)
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": 0.3,
            "max_tokens": 800,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            resp = httpx.post(url, json=payload, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except Exception as exc:
            log.error("External AI provider error: %s", exc)
            return f"[AI provider error: {exc}]"


# ---------------------------------------------------------------------------
# Predictive / risk scoring (rule-based, no ML)
# ---------------------------------------------------------------------------

RISK_WEIGHTS = {
    "months_delayed_high": 30,    # > 6 months delayed
    "probability_low": 25,        # probability < 20%
    "late_close_date": 20,        # close date past today
    "category_pipeline": 15,      # still in Pipeline (not Commit/Closed)
    "no_owner": 10,               # no opportunity owner
}


def compute_risk_score(opp) -> dict:
    """
    Rule-based risk score 0–100 with human-readable 'why' factors.
    Higher = more at risk of slipping or not closing.
    """
    score = 0
    factors: list[str] = []

    if (opp.get("months_delayed") or 0) > 6:
        score += RISK_WEIGHTS["months_delayed_high"]
        factors.append(f"Delayed {opp['months_delayed']:.0f} months")

    prob = opp.get("probability_pct") or 0
    if prob < 20:
        score += RISK_WEIGHTS["probability_low"]
        factors.append(f"Low probability ({prob:.0f}%)")

    cd = opp.get("close_date")
    if cd and str(cd) < date.today().isoformat():
        score += RISK_WEIGHTS["late_close_date"]
        factors.append("Close date in the past")

    if opp.get("forecast_category") == "Pipeline":
        score += RISK_WEIGHTS["category_pipeline"]
        factors.append("Still in Pipeline stage")

    if not opp.get("opportunity_owner"):
        score += RISK_WEIGHTS["no_owner"]
        factors.append("No owner assigned")

    return {
        "score": min(score, 100),
        "level": "High" if score >= 60 else "Medium" if score >= 30 else "Low",
        "factors": factors,
    }


# ---------------------------------------------------------------------------
# Main AIService
# ---------------------------------------------------------------------------

class AIService:
    def __init__(self, db: Session):
        self.db = db
        self.analytics = AnalyticsService(db)

    def _get_provider(self, ctx: UserContext) -> AIProvider:
        mode = settings.AI_PROVIDER.lower()
        if mode == "demo" or not settings.AI_API_KEY:
            return DemoProvider(self.analytics, ctx)
        return ExternalProvider()

    def _build_system_prompt(self, ctx: UserContext) -> str:
        kpis = self.analytics.get_kpis(ctx)
        approval = self.analytics.get_approval_status(ctx)
        # Build a compact summary — NEVER send raw opportunity rows
        summary = {
            "total_acv_usd": kpis.get("total_acv"),
            "total_opportunities": kpis.get("total_count"),
            "commit_acv": kpis.get("commit_acv"),
            "closed_acv": kpis.get("closed_acv"),
            "approval_breakdown": [
                {"status": r["approval_status"], "count": r["count"], "acv": r["acv"]}
                for r in approval.get("rows", [])
            ],
        }
        return (
            "You are the Mobileum Horizon AI assistant. "
            "You help the sales team understand the renewals pipeline. "
            "Answer concisely in 2–4 sentences using the aggregated data below. "
            "Format currency as $X.XXM. Never reveal raw row data.\n\n"
            f"PIPELINE SUMMARY (as of today):\n{json.dumps(summary, indent=2)}"
        )

    def ask(self, ctx: UserContext, question: str) -> dict:
        provider = self._get_provider(ctx)
        system = self._build_system_prompt(ctx)
        answer = provider.chat(system, question)
        return {"answer": answer, "provider": settings.AI_PROVIDER}

    def daily_brief(self, ctx: UserContext) -> dict:
        kpis = self.analytics.get_kpis(ctx)
        acv_changes = self.analytics.get_acv_changes(ctx)
        approval = self.analytics.get_approval_status(ctx)

        top_changes = acv_changes.get("rows", [])[:5]
        changes_text = "\n".join(
            f"- {r['opportunity_name']}: {r['old_value']} → {r['new_value']}"
            for r in top_changes
        ) or "No ACV changes detected since yesterday."

        question = (
            f"Generate a 3-sentence executive daily brief for the renewals pipeline. "
            f"Total ACV ${kpis.get('total_acv', 0)/1_000_000:.2f}M, "
            f"{kpis.get('total_count', 0):,} opportunities. "
            f"Top ACV changes: {changes_text}"
        )
        provider = self._get_provider(ctx)
        brief = provider.chat(
            "You are a concise executive briefing assistant for Mobileum renewals.",
            question,
        )
        return {"brief": brief, "generated_at": date.today().isoformat()}

    def predictive_insights(self, ctx: UserContext) -> dict:
        """
        Rule-based risk scores and slippage alerts.
        Shows 'collecting history' until 7+ snapshots exist.
        """
        from backend.models.snapshot import UploadSnapshot
        snap_count = self.db.query(UploadSnapshot).count()

        if snap_count < 7:
            return {
                "status": "collecting_history",
                "message": f"Collecting history — {snap_count}/7 snapshots loaded. Predictive insights will appear after 7 days of data.",
                "at_risk": [],
                "anomalies": [],
            }

        from backend.models.opportunity import Opportunity
        snap = self.analytics.get_active_snapshot(ctx)
        if snap is None:
            return {"status": "no_data", "at_risk": [], "anomalies": []}

        opps = self.analytics._opps_for(snap)
        at_risk = []
        for o in opps:
            opp_dict = {
                "opportunity_id_18": o.opportunity_id_18,
                "opportunity_name": o.opportunity_name,
                "forecast_category": o.forecast_category,
                "probability_pct": o.probability_pct,
                "close_date": str(o.close_date) if o.close_date else None,
                "months_delayed": o.months_delayed,
                "opportunity_owner": o.opportunity_owner,
            }
            risk = compute_risk_score(opp_dict)
            if risk["score"] >= 30:
                at_risk.append({**opp_dict, "risk": risk})

        at_risk.sort(key=lambda x: x["risk"]["score"], reverse=True)

        return {
            "status": "ok",
            "at_risk_count": len(at_risk),
            "at_risk": at_risk[:50],  # top 50
            "anomalies": [],  # future: statistical anomaly detection
        }
