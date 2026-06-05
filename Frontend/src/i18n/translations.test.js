import { describe, it, expect } from 'vitest'
import { translations } from './translations.js'

// Keys that every UI language must define
const REQUIRED_KEYS = [
  'nav.home',
  'nav.record',
  'nav.autopilot',
  'nav.settings',
  'home.startConversation',
  'home.startRecording',
  'home.stopRecording',
  'record.title',
  'record.noRecords',
  'settings.title',
  'http.timeout',
  'http.networkFail',
]

function resolveKey(obj, key) {
  return key.split('.').reduce((cur, part) => cur?.[part], obj)
}

describe('translations', () => {
  it('exports translations for both supported languages', () => {
    expect(translations).toHaveProperty('en')
    expect(translations).toHaveProperty('zh')
  })

  it.each(REQUIRED_KEYS)(
    'en has key "%s"',
    (key) => {
      expect(resolveKey(translations.en, key)).toBeTypeOf('string')
    },
  )

  it.each(REQUIRED_KEYS)(
    'zh has key "%s"',
    (key) => {
      expect(resolveKey(translations.zh, key)).toBeTypeOf('string')
    },
  )

  it('en and zh have the same top-level sections', () => {
    expect(Object.keys(translations.en).sort()).toEqual(Object.keys(translations.zh).sort())
  })

  it('resolved key returns undefined for a missing path', () => {
    expect(resolveKey(translations.en, 'nonexistent.key')).toBeUndefined()
  })
})
