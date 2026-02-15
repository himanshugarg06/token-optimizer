import bcrypt from 'bcryptjs'
import { randomBytes } from 'crypto'

const API_KEY_PREFIX = 'tok_'
const API_KEY_LENGTH = 32
const BCRYPT_SALT_ROUNDS = 10

/**
 * Generate a new random API key
 * Format: tok_[32 random characters]
 */
export function generateApiKey(): string {
  const randomPart = randomBytes(API_KEY_LENGTH)
    .toString('base64')
    .replace(/[+/=]/g, '')
    .slice(0, API_KEY_LENGTH)

  return `${API_KEY_PREFIX}${randomPart}`
}

/**
 * Hash an API key using bcrypt
 */
export async function hashApiKey(key: string): Promise<string> {
  return bcrypt.hash(key, BCRYPT_SALT_ROUNDS)
}

/**
 * Verify an API key against its hash
 */
export async function verifyApiKey(key: string, hash: string): Promise<boolean> {
  return bcrypt.compare(key, hash)
}

/**
 * Extract the key prefix for display (first 12 characters)
 * Example: tok_abcdefgh... -> tok_abcdefgh
 */
export function getKeyPrefix(key: string): string {
  return key.slice(0, 12)
}
