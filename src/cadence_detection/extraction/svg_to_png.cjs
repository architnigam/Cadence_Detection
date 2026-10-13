// Rasterize local SVG bytes on stdin; Python validates resource references first.
const sharp = require(require('node:path').resolve(process.argv[2]));
const chunks = [];
process.stdin.on('data', chunk => chunks.push(chunk));
process.stdin.on('end', async () => {
  try {
    const data = await sharp(Buffer.concat(chunks), {density: 144, limitInputPixels: Number(process.argv[3])})
      .resize({width: 1600, height: 1600, fit: 'inside'}).png().toBuffer();
    process.stdout.write(data);
  } catch (_) { process.exitCode = 1; }
});
