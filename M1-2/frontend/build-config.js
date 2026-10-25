// Vercel 빌드 단계에서 실행: 환경 변수 API_BASE_URL → config.js
// 정적 바닐라 사이트는 런타임에 환경 변수를 읽을 수 없으므로 빌드 시 파일로 굽는다.
const fs = require("fs");
const path = require("path");

const url = (process.env.API_BASE_URL || "").trim().replace(/\/+$/, "");
if (!url) {
  console.error("API_BASE_URL 환경 변수가 비어 있습니다. Vercel 프로젝트 설정에서 추가하세요.");
  process.exit(1);
}
if (!/^https?:\/\//.test(url)) {
  console.error(`API_BASE_URL 은 http(s):// 로 시작해야 합니다: ${url}`);
  process.exit(1);
}

const out = `// build-config.js 가 생성한 파일입니다.\nwindow.APP_CONFIG = ${JSON.stringify({ API_BASE_URL: url })};\n`;
fs.writeFileSync(path.join(__dirname, "config.js"), out);
console.log(`config.js 생성: API_BASE_URL=${url}`);
