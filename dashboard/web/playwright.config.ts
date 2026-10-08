import { defineConfig } from '@playwright/test'

// Assumes `make dashboard` (api :8000, web :5173) is already running against
// fixtures -- this config does not start servers itself, since the API half
// is a separate Python process (see Makefile).
export default defineConfig({
  testDir: './tests',
  use: {
    baseURL: 'http://localhost:5173',
  },
})
