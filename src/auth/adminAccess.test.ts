import { describe, expect, it } from 'vitest'
import { getAdminAccess, getAdminDestination } from './adminAccess'

describe('admin access routing', () => {
  it('separates unauthenticated, normal user and administrator access', () => {
    expect(getAdminAccess(null)).toBe('login')
    expect(getAdminAccess({ role: 'user' })).toBe('forbidden')
    expect(getAdminAccess({ role: 'admin' })).toBe('granted')
  })

  it('only accepts safe administrator destinations', () => {
    expect(getAdminDestination({ from: '/admin/jobs' })).toBe('/admin/jobs')
    expect(getAdminDestination({ from: '/admin/login' })).toBe('/admin/overview')
    expect(getAdminDestination({ from: '//example.com/admin' })).toBe('/admin/overview')
    expect(getAdminDestination({ from: '/profile' })).toBe('/admin/overview')
  })
})
