import React from 'react'

interface Props {
  children: React.ReactNode
  fallback?: React.ReactNode
}

interface State {
  error: Error | null
  retryKey: number
}

export class ErrorBoundary extends React.Component<Props, State> {
  state: State = { error: null, retryKey: 0 }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error }
  }

  componentDidCatch(error: Error, info: { componentStack: string }) {
    console.error('[ErrorBoundary] caught:', error, info.componentStack)
  }

  render() {
    const { error, retryKey } = this.state
    if (error) {
      if (this.props.fallback) return this.props.fallback
      return (
        <div className="flex h-screen flex-col items-center justify-center gap-4 p-8 text-center">
          <p className="text-lg font-semibold text-destructive">Something went wrong</p>
          <p className="text-sm text-muted-foreground">{error.message}</p>
          <button
            className="rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground"
            onClick={() => this.setState(s => ({ error: null, retryKey: s.retryKey + 1 }))}
          >
            Try again
          </button>
        </div>
      )
    }
    return <div key={retryKey}>{this.props.children}</div>
  }
}

export default ErrorBoundary
