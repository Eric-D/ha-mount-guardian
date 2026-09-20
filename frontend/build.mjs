import { build, context } from 'esbuild';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const watch = process.argv.includes('--watch');

const outFile = resolve(
  __dirname,
  '../custom_components/addon_mount_guard/www/mount-guard-card.js'
);

/** @type {import('esbuild').BuildOptions} */
const options = {
  entryPoints: [resolve(__dirname, 'src/card.ts')],
  bundle: true,
  format: 'esm',
  target: 'es2020',
  minify: true,
  sourcemap: false,
  legalComments: 'none',
  outfile: outFile,
  banner: {
    js: '/* mount-guard-card — artefact de build, ne pas éditer directement. Sources : frontend/src/ */',
  },
  logLevel: 'info',
};

if (watch) {
  const ctx = await context(options);
  await ctx.watch();
  console.log('esbuild: watching…');
} else {
  await build(options);
  console.log(`esbuild: ${outFile}`);
}
