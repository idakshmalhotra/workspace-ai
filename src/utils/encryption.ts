/*
 Basic AES-256-GCM encryption utilities for Node/TypeScript.

 How it works
 - Uses a 32-byte symmetric key. Provide it via ENCRYPTION_KEY.
 - Key can be:
   - 32 raw bytes in base64 (recommended), or
   - Any passphrase (we will derive a key via scrypt using a salt from ENV or a default constant).
 - Uses AES-256-GCM with a 12-byte random IV per message.
 - Output format (base64): [version(1 byte)][iv(12 bytes)][ciphertext(...)] [authTag(16 bytes)]
   We concatenate these bytes and base64-encode the whole payload.

 Environment variables
 - ENCRYPTION_KEY: Base64-encoded 32 bytes (preferred), OR a passphrase string.
 - ENCRYPTION_SALT: Optional, used for scrypt if ENCRYPTION_KEY is a passphrase.

 Usage example
   import { encryptString, decryptString } from './utils/encryption';
   const token = encryptString('hello');
   const plain = decryptString(token);

   import { encryptBuffer, decryptBuffer } from './utils/encryption';
   const encrypted = encryptBuffer(Buffer.from([1,2,3]));
   const decrypted = decryptBuffer(encrypted);
*/

import crypto from 'crypto';

const VERSION = 1; // for future upgrades
const ALGO = 'aes-256-gcm';
const IV_LENGTH = 12; // recommended for GCM
const AUTH_TAG_LENGTH = 16; // 128-bit tag

function getKey(): Buffer {
  const raw = process.env.ENCRYPTION_KEY || '';
  // Try to interpret as base64 first (32 bytes expected)
  try {
    const b = Buffer.from(raw, 'base64');
    if (b.length === 32) return b;
  } catch {}

  // Fallback: derive key from passphrase using scrypt
  const passphrase = raw || 'change-this-passphrase';
  const salt = process.env.ENCRYPTION_SALT || 'workspace-ai-default-salt';
  return crypto.scryptSync(passphrase, salt, 32);
}

function pack(version: number, iv: Buffer, ciphertext: Buffer, tag: Buffer): string {
  const header = Buffer.from([version & 0xff]);
  const payload = Buffer.concat([header, iv, ciphertext, tag]);
  return payload.toString('base64');
}

function unpack(token: string): { version: number; iv: Buffer; ciphertext: Buffer; tag: Buffer } {
  const buf = Buffer.from(token, 'base64');
  if (buf.length < 1 + IV_LENGTH + AUTH_TAG_LENGTH) {
    throw new Error('Invalid token');
  }
  const version = buf[0];
  const iv = buf.subarray(1, 1 + IV_LENGTH);
  const tag = buf.subarray(buf.length - AUTH_TAG_LENGTH);
  const ciphertext = buf.subarray(1 + IV_LENGTH, buf.length - AUTH_TAG_LENGTH);
  return { version, iv, ciphertext, tag };
}

export function encryptBuffer(plaintext: Buffer, aad?: Buffer): string {
  const key = getKey();
  const iv = crypto.randomBytes(IV_LENGTH);
  const cipher = crypto.createCipheriv(ALGO, key, iv, { authTagLength: AUTH_TAG_LENGTH });
  if (aad) cipher.setAAD(aad);
  const ciphertext = Buffer.concat([cipher.update(plaintext), cipher.final()]);
  const tag = cipher.getAuthTag();
  return pack(VERSION, iv, ciphertext, tag);
}

export function decryptBuffer(token: string, aad?: Buffer): Buffer {
  const key = getKey();
  const { version, iv, ciphertext, tag } = unpack(token);
  if (version !== VERSION) throw new Error('Unsupported token version');
  const decipher = crypto.createDecipheriv(ALGO, key, iv, { authTagLength: AUTH_TAG_LENGTH });
  if (aad) decipher.setAAD(aad);
  decipher.setAuthTag(tag);
  const plaintext = Buffer.concat([decipher.update(ciphertext), decipher.final()]);
  return plaintext;
}

export function encryptString(plaintext: string, aad?: string): string {
  const aadBuf = aad ? Buffer.from(aad) : undefined;
  return encryptBuffer(Buffer.from(plaintext, 'utf8'), aadBuf);
}

export function decryptString(token: string, aad?: string): string {
  const aadBuf = aad ? Buffer.from(aad) : undefined;
  return decryptBuffer(token, aadBuf).toString('utf8');
}

export function generateKeyBase64(): string {
  return crypto.randomBytes(32).toString('base64');
}
