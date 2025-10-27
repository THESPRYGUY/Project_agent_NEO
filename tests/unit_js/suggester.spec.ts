import { describe, it, expect } from 'vitest'
import { suggestPersona } from '../../src/ui/suggester.js'

describe('suggester', () => {
  it('returns a suggestion', () => {
    const res = suggestPersona({ role: 'COO' } as any)
    expect(res).toBeTruthy()
  })
})

