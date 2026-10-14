"""
demo_router.py — Rule-based intent router for Demo Mode.

Maps user questions directly to the 7 read-only assistant tools.
All numbers in answers come strictly from tool results (to the exact cent).
Rejects out-of-scope questions politely with supported topics.
"""
from __future__ import annotations

import re
import logging
from typing import Any, Dict, List, Optional, Tuple

from backend.services.assistant_tools import AssistantTools

log = logging.getLogger(__name__)

POLITE_REFUSAL = (
    "I can only answer questions about the Mobileum renewals pipeline data.\n\n"
    "Here is what you can ask me:\n"
    "• **Pipeline KPIs & Totals**: *'What is the total ACV and count for 2026-10-05?'*\n"
    "• **Pipeline Changes**: *'What changed since yesterday?'* or *'What changed since last week?'*\n"
    "• **Variances & Movements**: *'Which region lost the most Commit?'*\n"
    "• **Top Opportunities**: *'Top 10 opportunities in Middle East'* or *'Top 5 opportunities in Roaming BU'*\n"
    "• **Approval Breakdown**: *'How many deals are Pending Approval?'* or *'Show approval breakdown'*\n"
    "• **Deal History**: *'Show history of 006Qp00000as0WCIAY'*\n"
    "• **Regional / BU Filtering**: *'How many opportunities and ACV in North America?'*"
)

OUT_OF_SCOPE_PATTERNS = [
    r"\b(capital of|weather|president|prime minister|recipe|joke|poem|song|story)\b",
    r"\b(python script|code for|javascript|html|css|sql query|hack|write a program)\b",
    r"\b(apple|microsoft|google|tesla|amazon|meta|nvidia)\b(?!\s+(?:opp|deal|pipeline))",
    r"\b(who are you|who made you|are you human|tell me about yourself)\b",
    r"\b(ignore previous instructions|system prompt|jailbreak|dan mode)\b",
]

KNOWN_REGIONS = [
    "North America",
    "Middle East",
    "Central & Eastern Europe",
    "Western Europe",
    "Latin America",
    "South Asia",
    "Southeast Asia",
    "East Asia",
    "Sub-Saharan Africa",
    "Africa",
    "Asia Pacific",
    "Europe",
]

KNOWN_BUS = [
    "Roaming",
    "Security",
    "Network",
    "Engagement and Experience",
    "Testing",
    "RA & FM",
    "Analytics",
]


class DemoRouter:
    """Deterministic, rule-based assistant router for demo mode."""

    def __init__(self, tools: AssistantTools):
        self.tools = tools

    def route_and_execute(self, query: str) -> Dict[str, Any]:
        """
        Parses query, runs matching tool(s), and formats a verified response.
        Returns a dict:
        {
            "answer": str,
            "tools_called": list,
            "sources": list,
            "chart_data": dict | None,
            "is_refusal": bool,
        }
        """
        q = query.strip()
        q_lower = q.lower()

        # Check for out-of-scope queries
        for pat in OUT_OF_SCOPE_PATTERNS:
            if re.search(pat, q_lower):
                return {
                    "answer": POLITE_REFUSAL,
                    "tools_called": [],
                    "sources": [],
                    "chart_data": None,
                    "is_refusal": True,
                }

        # Check date patterns in query (e.g. 2026-10-05)
        date_match = re.search(r"\b(202\d-\d{2}-\d{2})\b", q)
        extracted_date = date_match.group(1) if date_match else None

        # Check 18-char opportunity ID pattern
        opp_id_match = re.search(r"\b(006[A-Za-z0-9]{15})\b", q)

        # -------------------------------------------------------------------
        # 1. Opportunity History
        # -------------------------------------------------------------------
        if ("history" in q_lower or "trend" in q_lower or "deal timeline" in q_lower or opp_id_match) and ("opp" in q_lower or "deal" in q_lower or opp_id_match):
            target_id = opp_id_match.group(1) if opp_id_match else None
            if not target_id:
                # Find any word that looks like an ID
                words = q.split()
                for w in words:
                    if len(w) >= 15 and w.isalnum():
                        target_id = w
                        break

            if target_id:
                res = self.tools.opportunity_history(target_id)
                if res.get("status") == "success":
                    nums = res["numbers"]
                    timeline = res["timeline"]
                    earliest_date = timeline[0]["snapshot_date"] if timeline else "N/A"
                    latest_date = timeline[-1]["snapshot_date"] if timeline else "N/A"
                    opp_name = res.get("opportunity_name", target_id)
                    cur_acv = f"${nums['current_acv']:,.2f}"
                    change_sign = "+" if nums["net_acv_change"] >= 0 else "-"
                    change_val = f"${abs(nums['net_acv_change']):,.2f}"

                    answer = (
                        f"**Opportunity History for `{target_id}`** ({opp_name}):\n\n"
                        f"• **Current ACV**: {cur_acv} (Category: **{nums['current_category']}**, Status: **{nums['current_approval']}**)\n"
                        f"• **Initial ACV**: ${nums['initial_acv']:,.2f} on {earliest_date}\n"
                        f"• **Net Change**: {change_sign}{change_val} across {nums['snapshots_present']} snapshot(s)\n"
                        f"• **Account**: {res.get('account_name', 'N/A')}\n\n"
                        f"Click the opportunity link or the chart below to inspect detailed changes."
                    )
                    return {
                        "answer": answer,
                        "tools_called": [{"tool": "opportunity_history", "args": {"id": target_id}, "result": res}],
                        "sources": [{"label": f"Opportunity {target_id}", "link": res["link"]}],
                        "chart_data": res.get("chart_data"),
                        "is_refusal": False,
                    }

        # -------------------------------------------------------------------
        # 2. What changed since yesterday / last week / comparison
        # -------------------------------------------------------------------
        if any(w in q_lower for w in ["what changed", "changes since", "changed since", "compare with", "difference since", "pipeline change"]):
            is_last_week = "last week" in q_lower
            d_today, d_baseline = self.tools._get_default_dates()
            if is_last_week:
                # Find snapshot older than yesterday
                snaps = self.tools.db.query(self.tools.analytics.models["snapshot"] if hasattr(self.tools.analytics, "models") else None).all() if False else None
                from backend.models.snapshot import UploadSnapshot
                lw_snap = (
                    self.tools.db.query(UploadSnapshot)
                    .filter(UploadSnapshot.snapshot_date < d_baseline)
                    .order_by(UploadSnapshot.snapshot_date.desc())
                    .first()
                )
                if lw_snap:
                    d_baseline = lw_snap.snapshot_date

            res = self.tools.compare(d_baseline.isoformat(), d_today.isoformat())
            if res.get("status") == "success":
                nums = res["numbers"]
                delta_sign = "+" if nums["delta_acv"] >= 0 else "-"
                delta_str = f"{delta_sign}${abs(nums['delta_acv']):,.2f}"
                cnt_sign = "+" if nums["delta_count"] >= 0 else ""
                period_label = "last week" if is_last_week else "yesterday"

                answer = (
                    f"**Pipeline Movement ({period_label.title()} vs Today)**:\n\n"
                    f"• **Net ACV Change**: **{delta_str}** (${nums['start_acv']:,.2f} → **${nums['end_acv']:,.2f}**)\n"
                    f"• **Opportunities Count**: **{cnt_sign}{nums['delta_count']:,}** ({nums['start_count']:,} → **{nums['end_count']:,}**)\n"
                    f"• **New Deals**: +${nums['new_acv']:,.2f}\n"
                    f"• **Increases**: +${nums['increases_acv']:,.2f}\n"
                    f"• **Decreases**: -${nums['decreases_acv']:,.2f}\n"
                    f"• **Removed**: -${nums['removed_acv']:,.2f}"
                )
                return {
                    "answer": answer,
                    "tools_called": [{"tool": "compare", "args": {"date_a": d_baseline.isoformat(), "date_b": d_today.isoformat()}, "result": res}],
                    "sources": [{"label": f"Waterfall ({d_baseline} → {d_today})", "link": res["link"]}],
                    "chart_data": None,
                    "is_refusal": False,
                }

        # -------------------------------------------------------------------
        # 3. Which region / BU / category lost or gained the most (Commit or Overall)
        # -------------------------------------------------------------------
        if ("lost the most" in q_lower or "gained the most" in q_lower or "largest decrease" in q_lower or "largest increase" in q_lower or "movement summary" in q_lower):
            group_by = "region" if "region" in q_lower else "bu" if ("bu" in q_lower or "business unit" in q_lower) else "category" if "category" in q_lower else "region"
            res = self.tools.movement_summary(group_by=group_by)
            if res.get("status") == "success":
                nums = res["numbers"]
                if "commit" in q_lower and nums.get("top_commit_loser"):
                    t_commit = nums["top_commit_loser"]
                    answer = (
                        f"Based on daily snapshot movements, the **{group_by}** that lost the most **Commit ACV** is **{t_commit['group']}**, "
                        f"with a net change of **-${abs(t_commit['commit_delta']):,.2f}** in Commit pipeline."
                    )
                elif "gain" in q_lower and nums.get("top_gainer"):
                    tg = nums["top_gainer"]
                    answer = (
                        f"The **{group_by}** with the highest ACV gain is **{tg['group']}**, "
                        f"with a net increase of **+${tg['delta_acv']:,.2f}** (from ${tg['start_acv']:,.2f} to ${tg['end_acv']:,.2f})."
                    )
                elif nums.get("top_loser"):
                    tl = nums["top_loser"]
                    answer = (
                        f"The **{group_by}** with the largest ACV decrease is **{tl['group']}**, "
                        f"with a net decrease of **-${abs(tl['delta_acv']):,.2f}** (from ${tl['start_acv']:,.2f} to ${tl['end_acv']:,.2f})."
                    )
                else:
                    answer = f"No significant negative movements detected across {group_by}s."

                return {
                    "answer": answer,
                    "tools_called": [{"tool": "movement_summary", "args": {"group_by": group_by}, "result": res}],
                    "sources": [{"label": f"{group_by.title()} Movements", "link": res["link"]}],
                    "chart_data": None,
                    "is_refusal": False,
                }

        # -------------------------------------------------------------------
        # 4. Top N opportunities (overall, region, BU)
        # -------------------------------------------------------------------
        if "top" in q_lower and any(w in q_lower for w in ["opportunity", "opportunities", "deals"]):
            # Extract N
            n_match = re.search(r"\btop\s+(\d+)\b", q_lower)
            n = int(n_match.group(1)) if n_match else 10
            n = min(n, 50)

            filters: Dict[str, Any] = {}
            for r in KNOWN_REGIONS:
                if r.lower() in q_lower:
                    filters["sub_region"] = r
                    break
            for b in KNOWN_BUS:
                if b.lower() in q_lower:
                    filters["business_unit"] = b
                    break
            if extracted_date:
                filters["snapshot_date"] = extracted_date

            res = self.tools.top_opportunities(filters=filters, n=n)
            if res.get("status") == "success":
                opps = res.get("opportunities", [])
                lines = [
                    f"{i+1}. **{o['opportunity_name']}** (`{o['opportunity_id_18']}`) — **${o['forecast_acv_amount']:,.2f}** "
                    f"[{o.get('sub_region', '')} · {o.get('forecast_category', '')}]"
                    for i, o in enumerate(opps)
                ]
                scope_desc = f" in **{filters.get('sub_region') or filters.get('business_unit')}**" if filters else ""
                answer = (
                    f"**Top {len(opps)} Opportunities{scope_desc}** (Total Top ACV: **${res['numbers']['top_n_total_acv']:,.2f}**):\n\n"
                    + "\n".join(lines)
                )
                return {
                    "answer": answer,
                    "tools_called": [{"tool": "top_opportunities", "args": {"filters": filters, "n": n}, "result": res}],
                    "sources": [{"label": f"Top Opportunities{scope_desc}", "link": res["link"]}],
                    "chart_data": res.get("chart_data"),
                    "is_refusal": False,
                }

        # -------------------------------------------------------------------
        # 5. Approval Breakdown / Pending Approval
        # -------------------------------------------------------------------
        if any(w in q_lower for w in ["pending approval", "approval status", "approval breakdown", "how many approved", "how many deals are pending"]):
            filters = {}
            if extracted_date:
                filters["snapshot_date"] = extracted_date
            res = self.tools.approval_breakdown(filters)
            if res.get("status") == "success":
                nums = res["numbers"]
                b_lines = [
                    f"• **{r['status']}**: **{r['count']:,}** opps (**${r['acv']:,.2f}**, {r['pct_count']}%)"
                    for r in res.get("breakdown", [])
                ]
                answer = (
                    f"**Opportunity Approval Status Breakdown**:\n\n"
                    f"Currently, there are **{nums['pending_count']:,}** deals **Pending Approval** totaling **${nums['pending_acv']:,.2f}**.\n\n"
                    + "\n".join(b_lines)
                    + f"\n\n**Total Pipeline**: **{nums['total_count']:,}** opportunities (**${nums['total_acv']:,.2f}**)."
                )
                return {
                    "answer": answer,
                    "tools_called": [{"tool": "approval_breakdown", "args": {"filters": filters}, "result": res}],
                    "sources": [{"label": "Approvals Overview", "link": res["link"]}],
                    "chart_data": res.get("chart_data"),
                    "is_refusal": False,
                }

        # -------------------------------------------------------------------
        # 6. Specific region / BU count and ACV query (e.g. North America, Middle East)
        # -------------------------------------------------------------------
        matched_region = None
        for r in KNOWN_REGIONS:
            if r.lower() in q_lower:
                matched_region = r
                break

        matched_bu = None
        for b in KNOWN_BUS:
            if b.lower() in q_lower:
                matched_bu = b
                break

        if matched_region or matched_bu:
            filters = {}
            if matched_region:
                filters["sub_region"] = matched_region
            if matched_bu:
                filters["business_unit"] = matched_bu
            if extracted_date:
                filters["snapshot_date"] = extracted_date

            res = self.tools.run_filtered_query(filters)
            if res.get("status") == "success":
                nums = res["numbers"]
                title_scope = f"in **{matched_region or matched_bu}**"
                if extracted_date:
                    title_scope += f" on **{extracted_date}**"

                answer = (
                    f"**Pipeline Summary for {matched_region or matched_bu}**:\n\n"
                    f"• **Total Opportunities**: **{nums['matched_count']:,}**\n"
                    f"• **Total ACV**: **${nums['total_acv']:,.2f}**\n\n"
                    f"You can view and filter all {nums['matched_count']:,} records directly in the Opportunities view."
                )
                return {
                    "answer": answer,
                    "tools_called": [{"tool": "run_filtered_query", "args": {"structured_filters": filters}, "result": res}],
                    "sources": [{"label": f"{matched_region or matched_bu} Opportunities", "link": res["link"]}],
                    "chart_data": None,
                    "is_refusal": False,
                }

        # -------------------------------------------------------------------
        # 7. General KPIs / Totals (e.g. on 2026-10-05 or current)
        # -------------------------------------------------------------------
        if any(w in q_lower for w in ["kpi", "total", "pipeline", "acv", "overall", "count", "summary", "how much", "how many"]):
            res = self.tools.get_kpis(extracted_date)
            if res.get("status") == "success":
                nums = res["numbers"]
                d_used = res.get("date_used")
                answer = (
                    f"**Pipeline KPIs as of {d_used}**:\n\n"
                    f"• **Total ACV**: **${nums['total_acv']:,.2f}** across **{nums['total_count']:,}** opportunities\n"
                    f"• **Commit ACV**: **${nums['commit_acv']:,.2f}** ({nums['commit_count']:,} opps)\n"
                    f"• **Closed ACV**: **${nums['closed_acv']:,.2f}** ({nums['closed_count']:,} opps)\n"
                    f"• **Best Case ACV**: **${nums['best_case_acv']:,.2f}**\n"
                    f"• **Pipeline ACV**: **${nums['pipeline_acv']:,.2f}**"
                )
                return {
                    "answer": answer,
                    "tools_called": [{"tool": "get_kpis", "args": {"date": d_used}, "result": res}],
                    "sources": [{"label": f"Pipeline Overview ({d_used})", "link": res["link"]}],
                    "chart_data": None,
                    "is_refusal": False,
                }

        # Default fallback: polite refusal listing supported capabilities
        return {
            "answer": POLITE_REFUSAL,
            "tools_called": [],
            "sources": [],
            "chart_data": None,
            "is_refusal": True,
        }
