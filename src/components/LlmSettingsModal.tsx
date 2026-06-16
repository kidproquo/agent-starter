import { useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  InputAdornment,
  MenuItem,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material'
import CloseIcon from '@mui/icons-material/Close'
import VisibilityIcon from '@mui/icons-material/VisibilityOutlined'
import VisibilityOffIcon from '@mui/icons-material/VisibilityOffOutlined'
import { apiBase } from '../lib/apiBase'
import { formatUsd } from '../lib/pricing'

type Provider = 'anthropic' | 'openai' | 'gemini' | 'unknown'
type KeyState = { set: boolean; hint: string }

type LlmSettings = {
  model: string
  effort: string
  max_tokens: number
  current_provider: Provider
  keys: Record<'anthropic' | 'openai' | 'gemini', KeyState>
}

type PricingEntry = {
  input_per_mtok: number
  output_per_mtok: number
  cache_read_per_mtok: number
  cache_write_per_mtok: number
}

// Curated names shown at the top of the picker; the full LiteLLM list follows.
const FAVORITES = [
  'anthropic/claude-opus-4-8',
  'anthropic/claude-sonnet-4-6',
  'anthropic/claude-haiku-4-5',
  'gpt-5.4',
  'gpt-5.4-mini',
  'gemini/gemini-2.5-pro',
  'gemini/gemini-2.5-flash',
]

function detectProvider(model: string): Provider {
  if (!model) return 'unknown'
  const bare = model.includes('/') ? model.split('/', 2)[1] : model
  if (bare.startsWith('claude-') || model.startsWith('anthropic/')) return 'anthropic'
  if (bare.startsWith('gpt-') || bare.startsWith('o1') || bare.startsWith('o3')) return 'openai'
  if (bare.startsWith('gemini-') || model.startsWith('gemini/')) return 'gemini'
  return 'unknown'
}

export function LlmSettingsModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [settings, setSettings] = useState<LlmSettings | null>(null)
  const [pricing, setPricing] = useState<Record<string, PricingEntry>>({})
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const [model, setModel] = useState('')
  const [effort, setEffort] = useState('medium')
  // Key fields start empty — we never receive the secret. A blank field on save
  // means "keep the stored key"; typing replaces it.
  const [keyInput, setKeyInput] = useState('')
  const [showKey, setShowKey] = useState(false)
  const [keyError, setKeyError] = useState<string | null>(null)
  const [validating, setValidating] = useState(false)
  const [validated, setValidated] = useState(false)

  useEffect(() => {
    if (!open) return
    let cancelled = false
    ;(async () => {
      setLoading(true)
      setError(null)
      setSuccess(null)
      setKeyInput('')
      setKeyError(null)
      setValidated(false)
      try {
        const [sRes, pRes] = await Promise.all([
          fetch(`${apiBase()}/admin/llm-settings`, { credentials: 'include' }),
          fetch(`${apiBase()}/models/pricing`, { credentials: 'include' }),
        ])
        if (!sRes.ok) throw new Error(`settings: HTTP ${sRes.status}`)
        const sData = (await sRes.json()) as LlmSettings
        const pData = pRes.ok
          ? ((await pRes.json()) as { models: Record<string, PricingEntry> })
          : { models: {} }
        if (cancelled) return
        setSettings(sData)
        setPricing(pData.models)
        setModel(sData.model)
        setEffort(sData.effort)
      } catch (e) {
        if (!cancelled) setError((e as Error).message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [open])

  const targetProvider = detectProvider(model)
  const currentKey: KeyState | undefined =
    settings && targetProvider !== 'unknown' ? settings.keys[targetProvider] : undefined

  const modelOptions = useMemo(() => {
    const known = new Set([...FAVORITES, ...Object.keys(pricing), settings?.model || ''])
    known.delete('')
    const favs = FAVORITES.filter((m) => known.has(m))
    const others = [...known].filter((m) => !FAVORITES.includes(m)).sort()
    return { favs, others }
  }, [pricing, settings?.model])

  const validate = async () => {
    if (!keyInput.trim()) return
    setValidating(true)
    setKeyError(null)
    setValidated(false)
    try {
      const res = await fetch(`${apiBase()}/admin/llm-settings/validate`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model, credential: keyInput }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = (await res.json()) as { valid: boolean; message: string }
      if (data.valid) setValidated(true)
      else setKeyError(data.message || 'invalid')
    } catch (e) {
      setKeyError((e as Error).message)
    } finally {
      setValidating(false)
    }
  }

  const apply = async () => {
    if (!settings) return
    setSaving(true)
    setError(null)
    setSuccess(null)
    setKeyError(null)
    try {
      const body: Record<string, unknown> = {}
      if (model !== settings.model) body.model = model
      if (effort !== settings.effort) body.effort = effort
      if (keyInput.trim() && targetProvider !== 'unknown') {
        body[`${targetProvider}_api_key`] = keyInput.trim()
      }
      if (Object.keys(body).length === 0) {
        setSuccess('Nothing changed.')
        setSaving(false)
        return
      }
      const res = await fetch(`${apiBase()}/admin/llm-settings`, {
        method: 'PUT',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (res.status === 400) {
        const data = (await res.json().catch(() => null)) as
          | { detail?: { validation_errors?: { field: string; message: string }[] } }
          | null
        const ve = data?.detail?.validation_errors ?? []
        setKeyError(ve[0]?.message ?? 'validation failed')
        setError('Validation failed — check the API key.')
        setSaving(false)
        return
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setSuccess('Saved. Takes effect on your next conversation.')
      setKeyInput('')
      setValidated(false)
      // Reflect the change locally so re-opening shows the new model/key state.
      setSettings({
        ...settings,
        model,
        effort,
        current_provider: targetProvider,
        keys: keyInput.trim()
          ? { ...settings.keys, [targetProvider]: { set: true, hint: `…${keyInput.trim().slice(-4)}` } }
          : settings.keys,
      })
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  const p = pricing[model] || pricing[model.includes('/') ? model.split('/')[1] : model]

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ pb: 1 }}>
        <Stack direction="row" alignItems="center" justifyContent="space-between">
          <Typography variant="h6" sx={{ fontSize: '1rem' }}>
            LLM model + API key
          </Typography>
          <IconButton size="small" onClick={onClose}>
            <CloseIcon fontSize="small" />
          </IconButton>
        </Stack>
        <Typography variant="caption" color="text.secondary">
          Admin only. Changes apply on the next conversation — no restart.
        </Typography>
      </DialogTitle>

      <DialogContent dividers>
        {loading && (
          <Stack alignItems="center" sx={{ py: 4 }}>
            <CircularProgress size={20} />
          </Stack>
        )}
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}
        {success && (
          <Alert severity="success" sx={{ mb: 2 }}>
            {success}
          </Alert>
        )}

        {!loading && settings && (
          <Stack spacing={2.5}>
            <Box>
              <TextField
                select
                fullWidth
                size="small"
                label="Model"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                helperText={`Provider: ${targetProvider}. Pricing from LiteLLM.`}
                SelectProps={{ MenuProps: { sx: { maxHeight: 480 } } }}
              >
                {modelOptions.favs.length > 0 && (
                  <MenuItem disabled value="" sx={{ opacity: 1, fontSize: '0.7rem' }}>
                    Recommended
                  </MenuItem>
                )}
                {modelOptions.favs.map((m) => (
                  <MenuItem key={m} value={m}>
                    <Typography sx={{ fontFamily: 'monospace', fontSize: '0.85rem' }}>{m}</Typography>
                  </MenuItem>
                ))}
                {modelOptions.others.length > 0 && (
                  <MenuItem disabled value="" sx={{ opacity: 1, fontSize: '0.7rem' }}>
                    All models LiteLLM recognizes
                  </MenuItem>
                )}
                {modelOptions.others.map((m) => (
                  <MenuItem key={m} value={m}>
                    <Typography sx={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>{m}</Typography>
                  </MenuItem>
                ))}
              </TextField>
              {p && (
                <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                  {formatUsd(p.input_per_mtok)} in / {formatUsd(p.output_per_mtok)} out per 1M tokens
                </Typography>
              )}
            </Box>

            <TextField
              select
              fullWidth
              size="small"
              label="Reasoning effort"
              value={effort}
              onChange={(e) => setEffort(e.target.value)}
              helperText="Passed to thinking-capable models; dropped for those that don't support it."
            >
              {['low', 'medium', 'high', 'xhigh', 'max'].map((v) => (
                <MenuItem key={v} value={v}>
                  {v}
                </MenuItem>
              ))}
            </TextField>

            {targetProvider === 'unknown' ? (
              <Alert severity="warning" variant="outlined">
                Provider for <code>{model}</code> not recognized — set its API key in the
                environment manually.
              </Alert>
            ) : (
              <Stack direction="row" spacing={1} alignItems="flex-start">
                <TextField
                  fullWidth
                  size="small"
                  label={`${targetProvider} API key`}
                  type={showKey ? 'text' : 'password'}
                  value={keyInput}
                  onChange={(e) => {
                    setKeyInput(e.target.value)
                    setValidated(false)
                    setKeyError(null)
                  }}
                  placeholder={
                    currentKey?.set ? `${currentKey.hint} — leave blank to keep` : '(not set)'
                  }
                  error={!!keyError}
                  helperText={
                    keyError ||
                    (validated
                      ? '✓ provider accepted the key'
                      : currentKey?.set
                        ? 'A key is stored. Type a new one to replace it.'
                        : 'No key stored for this provider yet.')
                  }
                  InputProps={{
                    endAdornment: (
                      <InputAdornment position="end">
                        {currentKey?.set && (
                          <Chip size="small" label="set" color="success" sx={{ mr: 0.5, height: 18 }} />
                        )}
                        <Tooltip title={showKey ? 'Hide' : 'Show'}>
                          <IconButton size="small" onClick={() => setShowKey((s) => !s)}>
                            {showKey ? (
                              <VisibilityOffIcon fontSize="small" />
                            ) : (
                              <VisibilityIcon fontSize="small" />
                            )}
                          </IconButton>
                        </Tooltip>
                      </InputAdornment>
                    ),
                  }}
                />
                <Button
                  variant="outlined"
                  size="small"
                  disabled={!keyInput.trim() || validating}
                  onClick={validate}
                  color={validated ? 'success' : 'primary'}
                  sx={{ mt: 0.25, minWidth: 90 }}
                >
                  {validating ? 'Testing…' : validated ? '✓ Valid' : 'Validate'}
                </Button>
              </Stack>
            )}
          </Stack>
        )}
      </DialogContent>

      <DialogActions>
        <Button onClick={onClose} size="small" disabled={saving}>
          Close
        </Button>
        <Button onClick={apply} variant="contained" size="small" disabled={loading || saving || !settings}>
          {saving ? 'Saving…' : 'Save'}
        </Button>
      </DialogActions>
    </Dialog>
  )
}
