import React, { Component, ErrorInfo, ReactNode } from 'react'
import { AlertTriangle, RefreshCw, Copy } from 'lucide-react'
import Card from '@/components/ui/Card'

interface Props {
  children?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
  errorInfo: ErrorInfo | null
}

class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
    errorInfo: null,
  }

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error, errorInfo: null }
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error:', error, errorInfo)
    this.setState({ errorInfo })
  }

  private handleCopy = () => {
    const text = `${this.state.error?.toString()}\n\n${this.state.errorInfo?.componentStack}`
    navigator.clipboard.writeText(text)
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="p-8 flex items-center justify-center min-h-[400px]">
          <Card className="max-w-lg w-full p-6 text-center shadow-xl border-red-500/20 bg-red-500/5 dark:bg-red-500/10">
            <div className="w-12 h-12 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center mx-auto mb-4 text-red-600 dark:text-red-400">
              <AlertTriangle className="w-6 h-6" />
            </div>
            <h2 className="text-lg font-bold text-[var(--text-primary)] mb-2">This page could not be displayed</h2>
            <p className="text-sm text-[var(--text-muted)] mb-6">
              An unexpected error occurred while rendering this page.
            </p>
            
            <div className="text-left bg-[var(--bg-primary)] p-3 rounded-lg border border-[var(--border)] overflow-auto max-h-40 mb-6">
              <pre className="text-[10px] font-mono text-red-600 dark:text-red-400 whitespace-pre-wrap">
                {this.state.error?.toString()}
              </pre>
            </div>

            <div className="flex justify-center gap-3">
              <button
                onClick={() => window.location.reload()}
                className="flex items-center gap-2 px-4 py-2 bg-[var(--primary)] text-white rounded-lg text-sm font-medium hover:bg-[var(--primary-hover)] transition-colors shadow-sm"
              >
                <RefreshCw className="w-4 h-4" />
                Reload page
              </button>
              <button
                onClick={this.handleCopy}
                className="flex items-center gap-2 px-4 py-2 bg-[var(--bg-secondary)] border border-[var(--border)] text-[var(--text-primary)] rounded-lg text-sm font-medium hover:bg-[var(--bg-tertiary)] transition-colors shadow-sm"
              >
                <Copy className="w-4 h-4" />
                Copy details
              </button>
            </div>
          </Card>
        </div>
      )
    }

    return this.props.children
  }
}

export default ErrorBoundary
