#!/usr/bin/env node
/** 将 scripts/landmarks_downtown.js 写入 shanghai_wutong_streets.html */
const fs = require('fs');
const path = require('path');
const landmarks = require('./landmarks_downtown.js');
const HTML_PATH = path.join(__dirname, '..', 'shanghai_wutong_streets.html');

function esc(s) {
  return String(s).replace(/\\/g, '\\\\').replace(/'/g, "\\'");
}

function serializeLandmarks(obj) {
  const lines = ['    const LANDMARKS_INFO = {'];
  for (const [key, lm] of Object.entries(obj)) {
    lines.push(`        ${key}: {`);
    lines.push(`            name: '${esc(lm.name)}',`);
    lines.push(`            category: '${lm.category}',`);
    lines.push(`            coords: [${lm.coords[0]}, ${lm.coords[1]}],`);
    lines.push(`            desc: '${esc(lm.desc)}',`);
    lines.push(`            mnemonic: '${esc(lm.mnemonic)}',`);
    lines.push(`            icon: '${lm.icon}'`);
    lines.push(`        },`);
  }
  lines.push('    };');
  return lines.join('\n');
}

let html = fs.readFileSync(HTML_PATH, 'utf8');
const block = serializeLandmarks(landmarks);
if (!html.match(/const LANDMARKS_INFO = \{/)) {
  console.error('LANDMARKS_INFO not found');
  process.exit(1);
}
html = html.replace(/const LANDMARKS_INFO = \{[\s\S]*?\n    \};/, block);
const n = Object.keys(landmarks).length;
html = html.replace(/渲染 \d+ 大文化地标/g, `渲染 ${n} 个地标`);
fs.writeFileSync(HTML_PATH, html);
console.log('Patched', n, 'landmarks into', HTML_PATH);
