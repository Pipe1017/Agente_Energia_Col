import { useState, useRef, useEffect } from 'react'
import { useMutation } from '@tanstack/react-query'
import { MessageCircle, X, Send, Loader2, Sparkles, User } from 'lucide-react'
import { chatApi } from '@/api'
import { useAppStore } from '@/stores/useAppStore'
import { cn } from '@/lib/utils'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

// Renderiza markdown básico de forma segura (sin dangerouslySetInnerHTML)
function MarkdownLine({ text }: { text: string }) {
  const parts = text.split(/(\*\*.*?\*\*)/g)
  return (
    <>
      {parts.map((part, i) =>
        part.startsWith('**') && part.endsWith('**')
          ? <strong key={i} className="font-semibold text-white">{part.slice(2, -2)}</strong>
          : part
      )}
    </>
  )
}

function MarkdownText({ content }: { content: string }) {
  const lines = content.split('\n')
  const elements: React.ReactNode[] = []
  let listBuffer: string[] = []

  function flushList() {
    if (!listBuffer.length) return
    elements.push(
      <ul key={`list-${elements.length}`} className="ml-3 space-y-0.5 list-none">
        {listBuffer.map((item, i) => (
          <li key={i} className="flex gap-1.5">
            <span className="text-zinc-500 shrink-0">•</span>
            <span><MarkdownLine text={item} /></span>
          </li>
        ))}
      </ul>
    )
    listBuffer = []
  }

  lines.forEach((line, i) => {
    const trimmed = line.trim()
    if (!trimmed) {
      flushList()
      elements.push(<div key={`sp-${i}`} className="h-1" />)
      return
    }
    if (trimmed.match(/^[-*]\s/)) {
      listBuffer.push(trimmed.slice(2))
      return
    }
    flushList()
    // Encabezados numéricos como "1. **Título**"
    if (trimmed.match(/^\d+\./)) {
      elements.push(
        <p key={i} className="mt-2">
          <MarkdownLine text={trimmed} />
        </p>
      )
      return
    }
    elements.push(<p key={i}><MarkdownLine text={trimmed} /></p>)
  })
  flushList()
  return <div className="space-y-1 text-zinc-200 leading-relaxed">{elements}</div>
}

const SUGGESTIONS = [
  '¿Por qué el precio spot está tan bajo?',
  '¿Qué estrategia de oferta recomiendas para mañana?',
  '¿Cómo está la hidrología vs el histórico?',
  '¿Cuál es el riesgo de despacho térmico?',
  '¿Cuándo activaría el precio de escasez?',
]

function MessageBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === 'user'
  return (
    <div className={cn('flex gap-2.5', isUser ? 'flex-row-reverse' : 'flex-row')}>
      <div className={cn(
        'flex-shrink-0 h-7 w-7 rounded-full flex items-center justify-center',
        isUser ? 'bg-blue-600' : 'bg-purple-700',
      )}>
        {isUser
          ? <User className="h-3.5 w-3.5 text-white" />
          : <Sparkles className="h-3.5 w-3.5 text-white" />
        }
      </div>
      <div className={cn(
        'max-w-[82%] rounded-2xl px-4 py-2.5 text-sm',
        isUser
          ? 'bg-blue-600 text-white rounded-tr-sm'
          : 'bg-zinc-800 rounded-tl-sm border border-zinc-700',
      )}>
        {isUser
          ? <p className="text-white leading-relaxed">{msg.content}</p>
          : <MarkdownText content={msg.content} />
        }
      </div>
    </div>
  )
}

export function ChatPanel() {
  const [open, setOpen] = useState(false)
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const agent = useAppStore((s) => s.selectedAgent)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const send = useMutation({
    mutationFn: ({ text }: { text: string }) =>
      chatApi.message(text, agent, messages.map((m) => ({ role: m.role, content: m.content }))),
    onSuccess: (data, { text }) => {
      setMessages((prev) => [
        ...prev,
        { role: 'user', content: text },
        { role: 'assistant', content: data.response },
      ])
    },
  })

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, send.isPending])

  // Limpiar conversación al cambiar agente
  useEffect(() => {
    setMessages([])
  }, [agent])

  function handleSend() {
    const text = input.trim()
    if (!text || send.isPending) return
    setInput('')
    send.mutate({ text })
  }

  function handleKey(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <>
      {/* Botón flotante */}
      <button
        onClick={() => setOpen(true)}
        className={cn(
          'fixed bottom-6 right-6 z-40 flex items-center gap-2 rounded-full shadow-lg px-4 py-3',
          'bg-purple-600 hover:bg-purple-500 text-white transition-all duration-200',
          open && 'opacity-0 pointer-events-none',
        )}
      >
        <MessageCircle className="h-5 w-5" />
        <span className="text-sm font-medium">Preguntar al agente</span>
      </button>

      {/* Panel */}
      <div className={cn(
        'fixed bottom-0 right-0 z-50 flex flex-col',
        'w-full sm:w-[420px] h-[600px] sm:h-[580px] sm:bottom-6 sm:right-6',
        'rounded-t-2xl sm:rounded-2xl border border-zinc-700 bg-zinc-950 shadow-2xl',
        'transition-all duration-300 origin-bottom-right',
        open ? 'scale-100 opacity-100' : 'scale-95 opacity-0 pointer-events-none',
      )}>
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800 shrink-0">
          <div className="flex items-center gap-2">
            <div className="h-7 w-7 rounded-full bg-purple-700 flex items-center justify-center">
              <Sparkles className="h-3.5 w-3.5 text-white" />
            </div>
            <div>
              <p className="text-sm font-semibold text-white">Agente Energía</p>
              <p className="text-xs text-zinc-500">Contexto: mercado actual · {agent}</p>
            </div>
          </div>
          <button
            onClick={() => setOpen(false)}
            className="rounded-lg p-1.5 text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Mensajes */}
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
          {messages.length === 0 && (
            <div className="space-y-4">
              <p className="text-xs text-center text-zinc-600">
                Haz preguntas sobre el mercado eléctrico colombiano.<br />
                Tengo contexto de datos reales en tiempo real.
              </p>
              <div className="space-y-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => { setInput(s); inputRef.current?.focus() }}
                    className="w-full text-left rounded-xl border border-zinc-800 bg-zinc-900 px-3 py-2 text-xs text-zinc-400 hover:border-zinc-600 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <MessageBubble key={i} msg={msg} />
          ))}

          {send.isPending && (
            <div className="flex gap-2.5">
              <div className="h-7 w-7 rounded-full bg-purple-700 flex items-center justify-center shrink-0">
                <Sparkles className="h-3.5 w-3.5 text-white" />
              </div>
              <div className="rounded-2xl rounded-tl-sm bg-zinc-800 border border-zinc-700 px-4 py-2.5">
                <Loader2 className="h-4 w-4 text-purple-400 animate-spin" />
              </div>
            </div>
          )}

          {send.isError && (
            <p className="text-center text-xs text-red-400">
              Error al conectar con el LLM. Intenta de nuevo.
            </p>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="px-4 pb-4 pt-2 border-t border-zinc-800 shrink-0">
          <div className="flex items-end gap-2 rounded-xl border border-zinc-700 bg-zinc-900 px-3 py-2 focus-within:border-zinc-500 transition-colors">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKey}
              placeholder="Pregunta sobre el mercado…"
              rows={1}
              className="flex-1 resize-none bg-transparent text-sm text-white placeholder-zinc-600 outline-none max-h-32 leading-5"
              style={{ height: '20px' }}
              onInput={(e) => {
                const el = e.currentTarget
                el.style.height = '20px'
                el.style.height = `${Math.min(el.scrollHeight, 128)}px`
              }}
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || send.isPending}
              className="shrink-0 rounded-lg bg-purple-600 hover:bg-purple-500 disabled:opacity-40 p-1.5 transition-colors"
            >
              <Send className="h-4 w-4 text-white" />
            </button>
          </div>
          <p className="mt-1.5 text-xs text-zinc-700 text-center">Enter para enviar · Shift+Enter para nueva línea</p>
        </div>
      </div>
    </>
  )
}
