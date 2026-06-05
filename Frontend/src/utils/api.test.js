import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock the axios instance before importing the API helpers
vi.mock('./request.js', () => ({
  default: vi.fn(),
}))

import request from './request.js'
import { getAPI, postAPI, putAPI, deleteListAPI } from './api.js'

beforeEach(() => {
  request.mockReset()
})

describe('api helpers', () => {
  it('getAPI calls request with method "get" and the given url', () => {
    getAPI('/settings', { foo: 1 })
    expect(request).toHaveBeenCalledWith({ method: 'get', url: '/settings', params: { foo: 1 } })
  })

  it('postAPI calls request with method "post" and the given body', () => {
    postAPI('/autopilot/run', { mode: 'text' })
    expect(request).toHaveBeenCalledWith({ method: 'post', url: '/autopilot/run', data: { mode: 'text' } })
  })

  it('putAPI calls request with method "put"', () => {
    putAPI('/settings', { connectors: {} })
    expect(request).toHaveBeenCalledWith({ method: 'put', url: '/settings', data: { connectors: {} } })
  })

  it('deleteListAPI calls request with method "delete"', () => {
    deleteListAPI('/items', { id: 42 })
    expect(request).toHaveBeenCalledWith({ method: 'delete', url: '/items', params: { id: 42 } })
  })

  it('extra config options are forwarded to request', () => {
    getAPI('/settings', undefined, { _suppressToast: true })
    expect(request).toHaveBeenCalledWith({
      method: 'get',
      url: '/settings',
      params: undefined,
      _suppressToast: true,
    })
  })
})
