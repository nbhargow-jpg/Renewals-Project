import toast from 'react-hot-toast'

export const showToast = {
  success: (message: string, description?: string) => {
    toast.success(
      <div>
        <div className="font-semibold text-sm">{message}</div>
        {description && (
          <div className="text-xs text-[var(--text-muted)] mt-0.5">{description}</div>
        )}
      </div>,
      {
        iconTheme: {
          primary: '#10B981',
          secondary: '#FFFFFF',
        },
      }
    )
  },

  error: (message: string, description?: string) => {
    toast.error(
      <div>
        <div className="font-semibold text-sm">{message}</div>
        {description && (
          <div className="text-xs text-[var(--text-muted)] mt-0.5">{description}</div>
        )}
      </div>,
      {
        iconTheme: {
          primary: '#EF4444',
          secondary: '#FFFFFF',
        },
      }
    )
  },

  info: (message: string, description?: string) => {
    toast(
      <div>
        <div className="font-semibold text-sm">{message}</div>
        {description && (
          <div className="text-xs text-[var(--text-muted)] mt-0.5">{description}</div>
        )}
      </div>,
      {
        icon: 'ℹ️',
      }
    )
  },

  warning: (message: string, description?: string) => {
    toast(
      <div>
        <div className="font-semibold text-sm">{message}</div>
        {description && (
          <div className="text-xs text-[var(--text-muted)] mt-0.5">{description}</div>
        )}
      </div>,
      {
        icon: '⚠️',
      }
    )
  },
}

export default showToast
