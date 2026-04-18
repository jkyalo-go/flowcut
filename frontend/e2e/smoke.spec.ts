import { expect, test } from '@playwright/test'

/**
 * Smoke-level E2E. Verifies that the app boots, unauth users are routed
 * to /login, and that the login form renders with expected labels.
 *
 * Deeper flows (invite accept, project create, upload, publish) land in
 * subsequent specs as the UI stabilizes.
 */

test('unauthenticated root redirects to login', async ({ page }) => {
  await page.goto('/')
  await expect(page).toHaveURL(/\/login/)
  await expect(page.getByRole('heading', { name: /sign in|log in|welcome/i })).toBeVisible()
})

test('login page has accessible email and password fields', async ({ page }) => {
  await page.goto('/login')
  const email = page.getByLabel(/email/i)
  const password = page.getByLabel(/password/i)
  await expect(email).toBeVisible()
  await expect(password).toBeVisible()
})

test('register page reachable from login', async ({ page }) => {
  await page.goto('/login')
  const registerLink = page.getByRole('link', { name: /register|sign up|create account/i })
  if (await registerLink.count()) {
    await registerLink.first().click()
    await expect(page).toHaveURL(/\/register/)
  }
})

test('health endpoints served via rewrite (backend up)', async ({ page }) => {
  const resp = await page.request.get('/api/auth/me')
  // 401 = backend reached and responded; a network error would throw
  expect([200, 401]).toContain(resp.status())
})
