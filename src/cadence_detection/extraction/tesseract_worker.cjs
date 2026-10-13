// Local assets only. This worker never downloads languages and never logs recognized text.
const readline = require('node:readline');
const path = require('node:path');
async function main() {
  const tess = require(path.resolve(process.argv[2]));
  const worker = await tess.createWorker(process.argv[4], 1, {
    langPath: path.resolve(process.argv[3]), gzip: false, cacheMethod: 'none',
    logger: () => {}, errorHandler: () => {},
  });
  for await (const line of readline.createInterface({input: process.stdin})) {
    try {
      const request = JSON.parse(line);
      await worker.setParameters({tessedit_pageseg_mode: request.sparse ? '11' : '3'});
      const result = await worker.recognize(request.path, {}, {text: false, tsv: true});
      process.stdout.write(JSON.stringify({ok: true, tsv: result.data.tsv}) + '\n');
    } catch (_) {
      process.stdout.write(JSON.stringify({ok: false}) + '\n');
    }
  }
  await worker.terminate();
}
main().catch(() => process.exit(1));
