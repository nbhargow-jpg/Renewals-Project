with open('frontend/src/pages/BusinessUnits.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update imports if needed
old_import = "import { formatACV, formatCount } from '@/utils/format'"
new_import = "import { formatACV, formatCount, formatCurrency, getForecastCategoryLabel } from '@/utils/format'"
if old_import in content:
    content = content.replace(old_import, new_import)

# 2. Add local state for the heatmap mode in the compact heatmap grid (Amount | Count | Both)
# Note: metricMode is already in store or we can have a local switch for this top heatmap
old_chart_section = """      {/* Chart Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Horizontal Stacked Bar */}
        <Card className="p-4 lg:col-span-2 flex flex-col min-h-[300px]">
          <h3 className="text-sm font-bold text-[var(--text-secondary)] mb-4">BU Forecast Distribution</h3>
          <div className="flex-1 flex flex-col gap-3 justify-center">
            {rows.map((r: any) => {
              const maxVal = metricMode === 'Count' ? total.count : total.acv
              const rVal = metricMode === 'Count' ? r.count : r.acv
              const widthPct = maxVal > 0 ? (rVal / maxVal) * 100 : 0
              if (widthPct === 0) return null

              return (
                <div key={r.bu} className="flex items-center gap-3">
                  <div className="w-24 shrink-0 text-xs font-medium text-[var(--text-secondary)] truncate text-right cursor-pointer hover:text-[var(--text-primary)]" onClick={() => handleDonutClick(r.bu)} title={r.bu}>
                    {r.bu}
                  </div>
                  <div className="flex-1 h-6 bg-[var(--bg-muted)] rounded-sm overflow-hidden flex relative group">
                    {categories.map((c: string) => {
                      const cVal = metricMode === 'Count' ? r.cells[c]?.count : r.cells[c]?.acv
                      if (!cVal) return null
                      const w = (cVal / rVal) * 100
                      return (
                        <div 
                          key={c}
                          className="h-full cursor-pointer hover:brightness-110 transition-all border-r border-[var(--bg-card)] last:border-r-0"
                          style={{ width: `${w}%`, backgroundColor: catColors[c] || '#ccc' }}
                          title={`${r.bu} - ${c}: ${metricMode === 'Count' ? cVal : formatACV(cVal)}`}
                          onClick={() => handleBarClick(r.bu, c)}
                        />
                      )
                    })}
                  </div>
                  <div className="w-16 shrink-0 text-xs text-[var(--text-muted)] text-right tabular-nums">
                    {metricMode === 'Count' ? rVal : formatACV(rVal)}
                  </div>
                </div>
              )
            })}
          </div>
          <div className="flex flex-wrap justify-center gap-3 mt-4">
            {categories.map((c: string) => (
              <div key={c} className="flex items-center gap-1.5 text-[10px] text-[var(--text-muted)]">
                <div className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: catColors[c] || '#ccc' }} />
                {c}
              </div>
            ))}
          </div>
        </Card>

        {/* Small Donut */}
        <Card className="p-4 flex flex-col min-h-[300px]">
          <h3 className="text-sm font-bold text-[var(--text-secondary)] mb-4">ACV Share</h3>
          <div className="flex-1 flex flex-col gap-2 overflow-y-auto pr-1">
            {rows.map((r: any, i: number) => {
              const color = donutColors[i % donutColors.length]
              return (
                <div 
                  key={r.bu} 
                  className="flex items-center justify-between p-2 rounded-md hover:bg-[var(--bg-muted)] cursor-pointer transition-colors"
                  onClick={() => handleDonutClick(r.bu)}
                >
                  <div className="flex items-center gap-2 overflow-hidden">
                    <div className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: color }} />
                    <span className="text-xs font-medium text-[var(--text-primary)] truncate">{r.bu}</span>
                  </div>
                  <div className="text-right shrink-0">
                    <div className="text-xs font-bold text-[var(--text-primary)]">{r.pct_acv}%</div>
                    <div className="text-[10px] text-[var(--text-muted)]">{formatACV(r.acv)}</div>
                  </div>
                </div>
              )
            })}
          </div>
        </Card>
      </div>"""

new_chart_section = """      {/* Replaced Chart Row: Compact Heatmap Grid + Ranked Bar of BU Share of Total ACV */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-5">
        {/* Compact Heatmap Grid (BU x Forecast Category) */}
        <div className="xl:col-span-8 flex flex-col">
          <CompactGrid
            title="BU x Forecast Category Heatmap"
            rowLabelName="Business Unit"
            columns={categories.filter((c: string) => c !== 'Pipeline')}
            rows={gridRows}
            totals={{ category: totals.categories, grand: totals.grand }}
            deltas={gridDeltas}
            metricMode={metricMode}
            onCellClick={handleCellClick}
            compareDate={prevDate}
            yesterdayDate={summary.yesterday_date}
            lastweekDate={summary.lastweek_date}
            heatMode={heatMode}
          />
        </div>

        {/* Ranked Bar: BU Share of Total ACV (Single colour, sorted, full untruncated labels, multi-value BUs retained) */}
        <Card className="xl:col-span-4 p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-[var(--text-primary)] font-display">
                BU Share of Total ACV
              </h3>
              <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-600 dark:text-indigo-400">
                {formatACV(total.acv)}
              </span>
            </div>

            <div className="space-y-3">
              {[...rows]
                .sort((a: any, b: any) => (b.acv || 0) - (a.acv || 0))
                .map((r: any) => {
                  const pct = total.acv > 0 ? (r.acv / total.acv) * 100 : 0
                  return (
                    <div
                      key={r.bu}
                      className="group cursor-pointer hover:bg-[var(--bg-muted)] p-2 rounded-lg transition-colors"
                      onClick={() => handleDonutClick(r.bu)}
                      title={`${r.bu}: ${formatCurrency(r.acv)} (${pct.toFixed(1)}% of total ACV) · Click to view deals`}
                    >
                      <div className="flex justify-between items-baseline text-xs mb-1">
                        <span className="font-semibold text-[var(--text-primary)] group-hover:text-indigo-600 transition-colors">
                          {r.bu}
                        </span>
                        <div className="flex items-center gap-2 font-mono">
                          <span className="font-bold text-[var(--text-primary)]">{pct.toFixed(1)}%</span>
                          <span className="text-[11px] text-[var(--text-muted)]">({formatACV(r.acv)})</span>
                        </div>
                      </div>
                      <div className="w-full h-2.5 bg-[var(--bg-muted)] rounded-full overflow-hidden border border-[var(--border)]">
                        <div
                          className="h-full bg-indigo-500 group-hover:bg-indigo-600 transition-all rounded-full"
                          style={{ width: `${Math.max(pct, 1)}%` }}
                        />
                      </div>
                    </div>
                  )
                })}
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-[var(--border)] text-[11px] text-[var(--text-muted)] flex items-center justify-between">
            <span>Ranked by ACV share · Multi-value BUs distinct</span>
            <span className="text-indigo-600 dark:text-indigo-400 font-semibold">Every row clickable →</span>
          </div>
        </Card>
      </div>"""

if old_chart_section in content:
    content = content.replace(old_chart_section, new_chart_section)
    print("Chart section replaced")
else:
    print("old_chart_section not found")

# Also ensure bottom matrix CompactGrid filters out Pipeline
content = content.replace("columns={categories}", "columns={categories.filter((c: string) => c !== 'Pipeline')}")

with open('frontend/src/pages/BusinessUnits.tsx', 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)
print("BusinessUnits patched successfully")
