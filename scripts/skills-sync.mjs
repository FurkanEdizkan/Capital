#!/usr/bin/env node
// Vendored-skills sync for Capital.
//
// The skills under .claude/skills/<name>/ are copied ("vendored") from upstream
// repositories and committed so every contributor and agent has them on clone,
// with no plugin or network install. This script tracks their versions in
// .claude/skills/skills-lock.json and updates them ON DEMAND.
//
//   node scripts/skills-sync.mjs check              # report drift (exit 1 if any)
//   node scripts/skills-sync.mjs update [names...]  # pull upstream + rewrite lock
//   node scripts/skills-sync.mjs update --yes       # non-interactive
//
// or: npm run skills:check  /  npm run skills:update
//
// Drift is decided by comparing the lock's recorded sha256 against a fresh
// upstream fetch (both LF), so it never depends on the local checkout's line
// endings. `check` is intentionally NOT wired into git hooks — updating skills
// is a deliberate choice, not something that should ever block a commit.

import { readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { createInterface } from 'node:readline/promises';
import { fileURLToPath } from 'node:url';
import { dirname, join, basename, resolve } from 'node:path';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const SKILLS_DIR = join(ROOT, '.claude', 'skills');
const LOCK_PATH = join(SKILLS_DIR, 'skills-lock.json');

const C = { reset: '\x1b[0m', dim: '\x1b[2m', red: '\x1b[31m', green: '\x1b[32m', yellow: '\x1b[33m', bold: '\x1b[1m' };
const paint = (s, c) => (process.stdout.isTTY ? c + s + C.reset : s);

const sha256 = (buf) => createHash('sha256').update(buf).digest('hex');
// Normalize to LF so a CRLF checkout can never masquerade as a real change.
const lf = (buf) => Buffer.from(buf.toString('utf8').replace(/\r\n/g, '\n'), 'utf8');

function repoOf(entry) {
  const m = /^github:(.+)$/.exec(entry.source);
  if (!m) throw new Error(`unsupported source "${entry.source}" (expected "github:owner/repo")`);
  return m[1];
}

async function fetchUpstream(entry) {
  const url = `https://raw.githubusercontent.com/${repoOf(entry)}/${entry.ref}/${entry.path}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`GET ${url} -> HTTP ${res.status}`);
  return lf(Buffer.from(await res.arrayBuffer()));
}

function remoteHead(entry) {
  const out = execFileSync('git', ['ls-remote', `https://github.com/${repoOf(entry)}.git`, entry.ref], { encoding: 'utf8' });
  const sha = out.split(/\s+/)[0];
  if (!/^[0-9a-f]{40}$/.test(sha || '')) throw new Error(`could not resolve ${repoOf(entry)}@${entry.ref}`);
  return sha;
}

const localPath = (name, entry) => join(SKILLS_DIR, name, basename(entry.path));
const readLock = () => JSON.parse(readFileSync(LOCK_PATH, 'utf8'));
const writeLock = (lock) => writeFileSync(LOCK_PATH, JSON.stringify(lock, null, 2) + '\n');

// Resolve one skill's current state: upstream bytes/hash, local integrity, drift.
async function inspect(name, entry) {
  const row = { name, entry, ok: true };
  try {
    row.upstream = await fetchUpstream(entry);
    row.upstreamSha = sha256(row.upstream);
  } catch (e) {
    row.ok = false;
    row.error = e.message;
    return row;
  }
  try {
    row.localSha = sha256(lf(readFileSync(localPath(name, entry))));
  } catch {
    row.localSha = null; // file missing locally
  }
  row.drift = row.upstreamSha !== entry.sha256;     // upstream moved since we vendored
  row.localModified = row.localSha !== entry.sha256; // working copy edited or missing
  return row;
}

async function check() {
  const lock = readLock();
  const rows = [];
  for (const [name, entry] of Object.entries(lock.skills)) rows.push(await inspect(name, entry));

  let drift = false, problems = false;
  console.log(paint('Vendored skill status', C.bold));
  for (const r of rows) {
    if (!r.ok) { problems = true; console.log(`  ${paint('✗', C.red)} ${r.name}  ${paint('fetch failed: ' + r.error, C.red)}`); continue; }
    const status = r.drift ? paint('UPDATE AVAILABLE', C.yellow) : paint('up to date', C.green);
    console.log(`  ${r.drift ? paint('↑', C.yellow) : paint('✓', C.green)} ${r.name.padEnd(24)} ${status}  ${paint(repoOf(r.entry) + '@' + r.entry.ref, C.dim)}`);
    if (r.drift) { drift = true; console.log(`      ${paint('locked ' + r.entry.sha256.slice(0, 12) + '  upstream ' + r.upstreamSha.slice(0, 12), C.dim)}`); }
    if (r.localModified) { problems = true; console.log(`      ${paint('! local .claude/skills/' + r.name + ' differs from the lock (hand-edited?) — re-run update to restore', C.red)}`); }
  }
  if (drift) console.log(`\nRun ${paint('npm run skills:update', C.bold)} to pull the latest (opt-in).`);
  else if (!problems) console.log(paint('\nAll vendored skills match their locked versions.', C.green));
  process.exit(drift || problems ? 1 : 0);
}

async function update(names, yes) {
  const lock = readLock();
  const targets = names.length ? names : Object.keys(lock.skills);
  const unknown = targets.filter((n) => !lock.skills[n]);
  if (unknown.length) { console.error(paint(`Unknown skill(s): ${unknown.join(', ')}`, C.red)); process.exit(2); }

  const changes = [];
  for (const name of targets) {
    const entry = lock.skills[name];
    const r = await inspect(name, entry);
    if (!r.ok) { console.error(paint(`  ✗ ${name}: ${r.error}`, C.red)); continue; }
    if (!r.drift && !r.localModified) { console.log(`  ${paint('✓', C.green)} ${name} already up to date`); continue; }
    changes.push({ name, entry, bytes: r.upstream, sha: r.upstreamSha });
  }
  if (!changes.length) { console.log(paint('Nothing to update.', C.green)); return; }

  console.log('\nWill update:');
  for (const c of changes) console.log(`  ${paint('↑', C.yellow)} ${c.name}  ${c.entry.sha256.slice(0, 12)} → ${c.sha.slice(0, 12)}`);

  if (!yes) {
    if (!process.stdin.isTTY) { console.error(paint('\nRefusing to write without confirmation. Re-run with --yes.', C.red)); process.exit(1); }
    const rl = createInterface({ input: process.stdin, output: process.stdout });
    const answer = (await rl.question('\nApply these updates? [y/N] ')).trim().toLowerCase();
    rl.close();
    if (answer !== 'y' && answer !== 'yes') { console.log('Aborted.'); return; }
  }

  const today = new Date().toISOString().slice(0, 10);
  for (const c of changes) {
    writeFileSync(localPath(c.name, c.entry), c.bytes);
    c.entry.sha256 = c.sha;
    try { c.entry.commit = remoteHead(c.entry); } catch { /* keep previous pin if ls-remote fails */ }
    c.entry.updatedAt = today;
  }
  writeLock(lock);
  console.log(paint(`\nUpdated ${changes.length} skill(s). Review the diff and commit.`, C.green));
}

const [cmd = 'check', ...rest] = process.argv.slice(2);
const yes = rest.includes('--yes') || rest.includes('-y');
const names = rest.filter((a) => !a.startsWith('-'));

try {
  if (cmd === 'check') await check();
  else if (cmd === 'update') await update(names, yes);
  else { console.error(`Usage:\n  node scripts/skills-sync.mjs check\n  node scripts/skills-sync.mjs update [names...] [--yes]`); process.exit(2); }
} catch (e) {
  console.error(paint(`skills-sync: ${e.message}`, C.red));
  process.exit(1);
}
