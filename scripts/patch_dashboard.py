with open('frontend/src/pages/Dashboard.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update imports
old_import = "import {\n  getV2OverviewSummary,\n  getV2OverviewMovements,\n  getV2RegionalBreakdown,\n} from '@/api/client'"
new_import = "import {\n  getV2OverviewSummary,\n  getV2OverviewMovements,\n  getV2RegionalBreakdown,\n  getV2OverviewDeals,\n} from '@/api/client'\nimport { getForecastCategoryLabel, formatCurrency, formatNumber } from '@/utils/format'"
if old_import in content:
    content = content.replace(old_import, new_import)
else:
    print("old_import not found")

# 2. Update FC_COLS to not include Pipeline
old_fc_cols = "const FC_COLS = ['Closed', 'Commit', 'Best Case', 'Pipeline', 'Blank'] as const"
new_fc_cols = "const FC_COLS = ['Closed', 'Commit', 'Best Case', 'Blank'] as const"
if old_fc_cols in content:
    content = content.replace(old_fc_cols, new_fc_cols)

# 3. Add helper to open modal by query
open_query_helper = """  const [modalInitialFilters, setModalInitialFilters] = useState<any>(undefined)

  const openDealsQuery = async (title: string, params: { category?: string; region?: string; approval_status?: string; kind?: string }, initialFilters?: any) => {
    try {
      const deals = await getV2OverviewDeals(params)
      setModalInitialFilters(initialFilters)
      setModal({ title, deals })
    } catch (err) {
      console.error('Failed to load deals', err)
    }
  }
"""

if 'const openDealsQuery =' not in content:
    content = content.replace("const [modal, setModal] = useState<{ title: string; deals: any[] } | null>(null)", "const [modal, setModal] = useState<{ title: string; deals: any[] } | null>(null)\n" + open_query_helper)

# 4. Total Q4 tile & comparison chips click handlers
old_s1 = """      {/* ── SECTION 1 – Total Renewal Q4 ACV Value ──────────────────────────── */}
      <div className="card-premium p-6">
        <div className="flex flex-wrap items-start justify-between gap-6">
          <div>
            <p className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-2">
              Total Renewal Q4 ACV Value
            </p>
            <div className="flex items-baseline gap-3">
              {sumLoading
                ? <div className="h-12 w-52 rounded-lg skeleton-shimmer" />
                : (
                  <span className="font-display font-extrabold text-4xl md:text-5xl text-gradient-brand tabular-nums">
                    ${(total.acv / 1_000_000).toFixed(2)}M
                  </span>
                )}
              <Pill color="teal"><Users className="w-3 h-3" />{total.count} Contracts</Pill>
            </div>
            <p className="text-[11px] text-[var(--text-muted)] mt-2">Fiscal Period = Q4 2026</p>
          </div>
          <div className="flex gap-3 flex-wrap">
            {[
              { label: 'vs Yesterday', delta: total.delta_yesterday },
              { label: 'vs Last Week', delta: total.delta_lastweek },
            ].map(({ label, delta }) => (
              <div key={label} className="card-premium px-4 py-3 min-w-[145px]">
                <p className="text-[11px] text-[var(--text-muted)] font-medium mb-2">{label}</p>
                {delta
                  ? <div className="flex flex-col gap-1"><DeltaBadge val={delta.count} label="deals" /><AcvDelta val={delta.acv} /></div>
                  : <span className="text-xs text-[var(--text-muted)]">\\u2014</span>}
              </div>
            ))}
          </div>
        </div>
      </div>"""

new_s1 = """      {/* ── SECTION 1 – Total Renewal Q4 ACV Value ──────────────────────────── */}
      <div className="card-premium p-6">
        <div className="flex flex-wrap items-start justify-between gap-6">
          <div
            className="cursor-pointer group"
            onClick={() => openDealsQuery(`Total Renewal Q4 Deals (${total.count} Contracts · ${formatCurrency(total.acv)})`, {})}
            title="Click to view all Q4 deals"
          >
            <p className="text-xs font-semibold text-[var(--text-muted)] group-hover:text-[var(--brand-teal)] uppercase tracking-wider mb-2 transition-colors">
              Total Renewal Q4 ACV Value
            </p>
            <div className="flex items-baseline gap-3">
              {sumLoading
                ? <div className="h-12 w-52 rounded-lg skeleton-shimmer" />
                : (
                  <span className="font-display font-extrabold text-4xl md:text-5xl text-gradient-brand tabular-nums group-hover:underline">
                    ${(total.acv / 1_000_000).toFixed(2)}M
                  </span>
                )}
              <Pill color="teal"><Users className="w-3 h-3" />{total.count} Contracts</Pill>
            </div>
            <p className="text-[11px] text-[var(--text-muted)] mt-2">Fiscal Period = Q4 2026 · Click to view all {total.count} contracts</p>
          </div>
          <div className="flex gap-3 flex-wrap">
            {[
              { label: 'vs Yesterday', delta: total.delta_yesterday, kind: 'delta_yesterday' },
              { label: 'vs Last Week', delta: total.delta_lastweek, kind: 'delta_lastweek' },
            ].map(({ label, delta, kind }) => (
              <div
                key={label}
                className="card-premium px-4 py-3 min-w-[145px] cursor-pointer hover:border-[var(--brand-teal)] transition-all"
                onClick={() => delta && openDealsQuery(`${label} Movement Deals (${delta.count} deals · ${acvM(delta.acv)})`, { kind })}
                title={`Click to view deals with changes ${label}`}
              >
                <p className="text-[11px] text-[var(--text-muted)] font-medium mb-2">{label}</p>
                {delta
                  ? <div className="flex flex-col gap-1"><DeltaBadge val={delta.count} label="deals" /><AcvDelta val={delta.acv} /></div>
                  : <span className="text-xs text-[var(--text-muted)]">\\u2014</span>}
              </div>
            ))}
          </div>
        </div>
      </div>"""

if old_s1 in content:
    content = content.replace(old_s1, new_s1)
else:
    print("old_s1 not found")

# 5. Replace Section 2 cards with [Closed] [Commit] [Best Case] [Not yet proposed]
# and Pipeline folded into the Not yet proposed card's footer
old_s2 = """      {/* ── SECTION 2 – Four category cards ─────────────────────────────────── */}
      <div>
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          {(['Closed', 'Commit', 'Best Case', 'Pipeline'] as const).map((fc) => {
            const cat = cats[fc] ?? { count: 0, acv: 0, delta_yesterday: null, delta_lastweek: null }
            const color = FORECAST_COLORS[fc]
            return (
              <motion.div
                key={fc}
                initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                className="card-premium p-5 flex flex-col gap-3"
                style={{ borderTop: `3px solid ${color}` }}
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider">{fc}</span>
                  <Pill color="slate"><Users className="w-3 h-3" />{cat.count} deals</Pill>
                </div>
                {sumLoading
                  ? <div className="h-8 w-28 skeleton-shimmer rounded" />
                  : <span className="font-display font-extrabold text-2xl tabular-nums" style={{ color }}>{acvM(cat.acv)}</span>}
                <hr className="border-[var(--border-subtle)]" />
                <div className="flex flex-col gap-1">
                  {[
                    { label: 'vs Yesterday', d: cat.delta_yesterday },
                    { label: 'vs Last Week', d: cat.delta_lastweek },
                  ].map(({ label, d }) => d && (
                    <div key={label} className="flex items-center justify-between text-[11px]">
                      <span className="text-[var(--text-muted)]">{label}</span>
                      <div className="flex gap-1"><DeltaBadge val={d.count} /><AcvDelta val={d.acv} /></div>
                    </div>
                  ))}
                </div>
              </motion.div>
            )
          })}
        </div>

        {/* Blank / Unassigned mini card */}
        {cats['Blank'] && cats['Blank'].count > 0 && (
          <div className="mt-3 flex justify-end">
            <div
              className="card-premium px-4 py-3 flex items-center gap-4"
              style={{ borderLeft: `3px solid ${FORECAST_COLORS['Blank']}` }}
            >
              <div>
                <p className="text-[11px] font-semibold text-[var(--text-muted)]">Blank / Unassigned</p>
                <p className="text-base font-bold tabular-nums text-[var(--text-secondary)]">{acvM(cats['Blank'].acv)}</p>
              </div>
              <Pill color="slate"><Users className="w-3 h-3" />{cats['Blank'].count} deals</Pill>
            </div>
          </div>
        )}
      </div>"""

new_s2 = """      {/* ── SECTION 2 – Four category cards in one row ──────────────────────── */}
      <div>
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          {([
            { key: 'Closed', label: 'Closed', dataKey: 'Closed' },
            { key: 'Commit', label: 'Commit', dataKey: 'Commit' },
            { key: 'Best Case', label: 'Best Case', dataKey: 'Best Case' },
            { key: 'Blank', label: 'Not yet proposed', dataKey: 'Blank' },
          ] as const).map(({ key, label, dataKey }) => {
            const cat = cats[dataKey] ?? { count: 0, acv: 0, delta_yesterday: null, delta_lastweek: null }
            const color = FORECAST_COLORS[dataKey] || '#64748b'
            const isBlank = key === 'Blank'
            const pipelineCat = cats['Pipeline'] ?? { count: 0, acv: 0 }

            return (
              <motion.div
                key={key}
                initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                className="card-premium p-5 flex flex-col justify-between gap-3 cursor-pointer hover:border-[var(--brand-teal)] transition-all"
                style={{ borderTop: `3px solid ${color}` }}
                onClick={() => openDealsQuery(`${label} Deals (${cat.count} deals · ${acvM(cat.acv)})`, { category: dataKey }, { forecast_category: dataKey })}
                title={`Click to view ${label} deals`}
              >
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider">{label}</span>
                    <Pill color="slate"><Users className="w-3 h-3" />{cat.count} deals</Pill>
                  </div>
                  {sumLoading
                    ? <div className="h-8 w-28 skeleton-shimmer rounded" />
                    : <span className="font-display font-extrabold text-2xl tabular-nums block hover:underline" style={{ color }}>{acvM(cat.acv)}</span>}
                  
                  <hr className="border-[var(--border-subtle)]" />
                  
                  <div className="flex flex-col gap-1">
                    {[
                      { l: 'vs Yesterday', d: cat.delta_yesterday },
                      { l: 'vs Last Week', d: cat.delta_lastweek },
                    ].map(({ l, d }) => d ? (
                      <div key={l} className="flex items-center justify-between text-[11px]">
                        <span className="text-[var(--text-muted)]">{l}</span>
                        <div className="flex gap-1"><DeltaBadge val={d.count} /><AcvDelta val={d.acv} /></div>
                      </div>
                    ) : (
                      <div key={l} className="flex items-center justify-between text-[11px] text-[var(--text-muted)] opacity-60">
                        <span>{l}</span>
                        <span>\\u2014</span>
                      </div>
                    ))}
                  </div>
                </div>

                {isBlank && (
                  <div
                    className="mt-2 pt-2 border-t border-[var(--border-subtle)] flex items-center justify-between text-[11px] text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                    onClick={(e) => {
                      e.stopPropagation()
                      if (pipelineCat.count > 0) {
                        openDealsQuery(`Other / Pipeline Deals (${pipelineCat.count} deal · ${acvM(pipelineCat.acv)})`, { category: 'Pipeline' }, { forecast_category: 'Pipeline' })
                      }
                    }}
                    title={`Sum check: Closed (${cats['Closed']?.count || 0}) + Commit (${cats['Commit']?.count || 0}) + Best Case (${cats['Best Case']?.count || 0}) + Not yet proposed (${cats['Blank']?.count || 0}) + Other (${pipelineCat.count || 0}) = ${total.count} deals ($${(total.acv / 1_000_000).toFixed(2)}M)`}
                  >
                    <span className="font-medium flex items-center gap-1">
                      <span className="w-2 h-2 rounded-full bg-amber-500 inline-block" />
                      Other / Pipeline:
                    </span>
                    <span className="font-mono font-bold text-amber-600 dark:text-amber-400 hover:underline">
                      {pipelineCat.count} deal ({acvM(pipelineCat.acv)})
                    </span>
                  </div>
                )}
              </motion.div>
            )
          })}
        </div>
      </div>"""

if old_s2 in content:
    content = content.replace(old_s2, new_s2)
else:
    print("old_s2 not found")

# 6. Proposal confirmation click-through
old_prop_cell = """                <tr key={row.region} className="hover:bg-[var(--bg-secondary)] transition-colors">
                  <td className="px-4 py-3 font-medium">{row.region}</td>
                  <td className="px-4 py-3 text-right font-mono font-bold">
                    {(row.approved_count ?? 0) + (row.pending_count ?? 0) + (row.blank_count ?? 0)}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-emerald-700 dark:text-emerald-400 font-bold">{row.approved_count ?? 0}</td>
                  <td className="px-4 py-3 text-right font-mono text-amber-700 dark:text-amber-400 font-bold">{row.pending_count ?? 0}</td>
                  <td className="px-4 py-3 text-right font-mono text-[var(--text-secondary)]">{row.blank_count ?? 0}</td>
                </tr>"""

new_prop_cell = """                <tr key={row.region} className="hover:bg-[var(--bg-secondary)] transition-colors">
                  <td className="px-4 py-3 font-medium cursor-pointer hover:underline" onClick={() => openDealsQuery(`${row.region} Deals`, { region: row.region }, { sub_region: row.region })}>{row.region}</td>
                  <td className="px-4 py-3 text-right font-mono font-bold cursor-pointer hover:underline text-[var(--brand-teal)]" onClick={() => openDealsQuery(`${row.region} · All Approvals`, { region: row.region }, { sub_region: row.region })}>
                    {(row.approved_count ?? 0) + (row.pending_count ?? 0) + (row.blank_count ?? 0)}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-emerald-700 dark:text-emerald-400 font-bold cursor-pointer hover:underline" onClick={() => openDealsQuery(`${row.region} · Approved Deals`, { region: row.region, approval_status: 'Approved' }, { sub_region: row.region, approval_status: 'Approved' })}>{row.approved_count ?? 0}</td>
                  <td className="px-4 py-3 text-right font-mono text-amber-700 dark:text-amber-400 font-bold cursor-pointer hover:underline" onClick={() => openDealsQuery(`${row.region} · Pending Approval Deals`, { region: row.region, approval_status: 'Pending Approval' }, { sub_region: row.region, approval_status: 'Pending Approval' })}>{row.pending_count ?? 0}</td>
                  <td className="px-4 py-3 text-right font-mono text-[var(--text-secondary)] cursor-pointer hover:underline" onClick={() => openDealsQuery(`${row.region} · Not submitted (Blank)`, { region: row.region, approval_status: 'Blank' }, { sub_region: row.region, approval_status: 'Blank' })}>{row.blank_count ?? 0}</td>
                </tr>"""

if old_prop_cell in content:
    content = content.replace(old_prop_cell, new_prop_cell)
else:
    print("old_prop_cell not found")

# Proposal confirmation totals row clickable
old_prop_tot = """              <tr className="bg-[var(--bg-secondary)] font-bold border-t-2 border-[var(--border)]">
                <td className="px-4 py-3">Total</td>
                <td className="px-4 py-3 text-right font-mono">
                  {(propTotals.approved_count ?? 0) + (propTotals.pending_count ?? 0) + (propTotals.blank_count ?? 0)}
                </td>
                <td className="px-4 py-3 text-right font-mono text-emerald-700 dark:text-emerald-400">{propTotals.approved_count ?? 0}</td>
                <td className="px-4 py-3 text-right font-mono text-amber-700 dark:text-amber-400">{propTotals.pending_count ?? 0}</td>
                <td className="px-4 py-3 text-right font-mono">{propTotals.blank_count ?? 0}</td>
              </tr>"""

new_prop_tot = """              <tr className="bg-[var(--bg-secondary)] font-bold border-t-2 border-[var(--border)]">
                <td className="px-4 py-3">Total</td>
                <td className="px-4 py-3 text-right font-mono cursor-pointer hover:underline text-[var(--brand-teal)]" onClick={() => openDealsQuery(`Total Opportunity Approvals (${(propTotals.approved_count ?? 0) + (propTotals.pending_count ?? 0) + (propTotals.blank_count ?? 0)} deals)`, {})}>
                  {(propTotals.approved_count ?? 0) + (propTotals.pending_count ?? 0) + (propTotals.blank_count ?? 0)}
                </td>
                <td className="px-4 py-3 text-right font-mono text-emerald-700 dark:text-emerald-400 cursor-pointer hover:underline" onClick={() => openDealsQuery(`All Approved Deals (${propTotals.approved_count ?? 0} deals)`, { approval_status: 'Approved' }, { approval_status: 'Approved' })}>{propTotals.approved_count ?? 0}</td>
                <td className="px-4 py-3 text-right font-mono text-amber-700 dark:text-amber-400 cursor-pointer hover:underline" onClick={() => openDealsQuery(`All Pending Approval Deals (${propTotals.pending_count ?? 0} deals)`, { approval_status: 'Pending Approval' }, { approval_status: 'Pending Approval' })}>{propTotals.pending_count ?? 0}</td>
                <td className="px-4 py-3 text-right font-mono cursor-pointer hover:underline" onClick={() => openDealsQuery(`All Not submitted (Blank) Deals (${propTotals.blank_count ?? 0} deals)`, { approval_status: 'Blank' }, { approval_status: 'Blank' })}>{propTotals.blank_count ?? 0}</td>
              </tr>"""

if old_prop_tot in content:
    content = content.replace(old_prop_tot, new_prop_tot)
else:
    print("old_prop_tot not found")

# 7. Regional Trend table headers and cells
old_trend_th = """                {FC_COLS.map(fc => (
                  <th key={fc} className="text-right px-4 py-3 font-semibold" style={{ color: FORECAST_COLORS[fc] }}>{fc}</th>
                ))}"""

new_trend_th = """                {FC_COLS.map(fc => (
                  <th key={fc} className="text-right px-4 py-3 font-semibold" style={{ color: FORECAST_COLORS[fc] }}>{getForecastCategoryLabel(fc)}</th>
                ))}"""

if old_trend_th in content:
    content = content.replace(old_trend_th, new_trend_th)
else:
    print("old_trend_th not found")

old_trend_row = """              {trendRows.map((row: any) => (
                <tr key={row.region} className="hover:bg-[var(--bg-secondary)] transition-colors">
                  <td className="px-4 py-3 font-medium">{row.region}</td>
                  <td className="px-4 py-3 text-right font-mono font-bold">{acvM(row.total_acv)}</td>
                  {FC_COLS.map(fc => {
                    const k = fc.toLowerCase().replace(' ', '_') + '_acv'
                    return <td key={fc} className="px-4 py-3 text-right font-mono" style={{ color: FORECAST_COLORS[fc] }}>{acvM(row[k] ?? 0)}</td>
                  })}
                </tr>
              ))}"""

new_trend_row = """              {trendRows.map((row: any) => (
                <tr key={row.region} className="hover:bg-[var(--bg-secondary)] transition-colors">
                  <td className="px-4 py-3 font-medium cursor-pointer hover:underline" onClick={() => openDealsQuery(`${row.region} Deals (${acvM(row.total_acv)})`, { region: row.region }, { sub_region: row.region })}>{row.region}</td>
                  <td className="px-4 py-3 text-right font-mono font-bold cursor-pointer hover:underline text-[var(--brand-teal)]" onClick={() => openDealsQuery(`${row.region} Total (${acvM(row.total_acv)})`, { region: row.region }, { sub_region: row.region })}>{acvM(row.total_acv)}</td>
                  {FC_COLS.map(fc => {
                    const k = fc.toLowerCase().replace(' ', '_') + '_acv'
                    const val = row[k] ?? 0
                    return (
                      <td
                        key={fc}
                        className="px-4 py-3 text-right font-mono cursor-pointer hover:underline"
                        style={{ color: FORECAST_COLORS[fc] }}
                        onClick={() => openDealsQuery(`${row.region} · ${getForecastCategoryLabel(fc)} (${acvM(val)})`, { region: row.region, category: fc }, { sub_region: row.region, forecast_category: fc })}
                      >
                        {acvM(val)}
                      </td>
                    )
                  })}
                </tr>
              ))}"""

if old_trend_row in content:
    content = content.replace(old_trend_row, new_trend_row)
else:
    print("old_trend_row not found")

old_trend_tot = """              <tr className="bg-[var(--bg-secondary)] font-bold border-t-2 border-[var(--border)]">
                <td className="px-4 py-3">Total</td>
                <td className="px-4 py-3 text-right font-mono">{acvM(regTotals.total_acv)}</td>
                {FC_COLS.map(fc => {
                  const k = fc.toLowerCase().replace(' ', '_') + '_acv'
                  return <td key={fc} className="px-4 py-3 text-right font-mono" style={{ color: FORECAST_COLORS[fc] }}>{acvM(regTotals[k] ?? 0)}</td>
                })}
              </tr>"""

new_trend_tot = """              <tr className="bg-[var(--bg-secondary)] font-bold border-t-2 border-[var(--border)]">
                <td className="px-4 py-3">Total</td>
                <td className="px-4 py-3 text-right font-mono cursor-pointer hover:underline text-[var(--brand-teal)]" onClick={() => openDealsQuery(`Total Renewal ACV (${acvM(regTotals.total_acv)})`, {})}>{acvM(regTotals.total_acv)}</td>
                {FC_COLS.map(fc => {
                  const k = fc.toLowerCase().replace(' ', '_') + '_acv'
                  const val = regTotals[k] ?? 0
                  return (
                    <td
                      key={fc}
                      className="px-4 py-3 text-right font-mono cursor-pointer hover:underline"
                      style={{ color: FORECAST_COLORS[fc] }}
                      onClick={() => openDealsQuery(`Total · ${getForecastCategoryLabel(fc)} (${acvM(val)})`, { category: fc }, { forecast_category: fc })}
                    >
                      {acvM(val)}
                    </td>
                  )
                })}
              </tr>"""

if old_trend_tot in content:
    content = content.replace(old_trend_tot, new_trend_tot)
else:
    print("old_trend_tot not found")

# 8. DealListModal prop update for initialFilters
old_modal_render = """      {/* Deal modal */}
      {modal && (
        <DealListModal
          title={modal.title}
          deals={modal.deals}
          onSelectOpp={(id) => { setModal(null); setSelectedOppId(id) }}
          onClose={() => setModal(null)}
        />
      )}"""

new_modal_render = """      {/* Deal modal */}
      {modal && (
        <DealListModal
          title={modal.title}
          deals={modal.deals}
          initialFilters={modalInitialFilters}
          onSelectOpp={(id) => { setModal(null); setSelectedOppId(id) }}
          onClose={() => { setModal(null); setModalInitialFilters(undefined) }}
        />
      )}"""

if old_modal_render in content:
    content = content.replace(old_modal_render, new_modal_render)
else:
    print("old_modal_render not found")

with open('frontend/src/pages/Dashboard.tsx', 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)
print("Dashboard patched successfully")
