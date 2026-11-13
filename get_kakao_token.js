const fs = require('fs');
const path = require('path');

async function getKakaoToken(authCode) {
    if (!authCode) {
        console.error('사용법: node get_kakao_token.js <인가코드>');
        process.exit(1);
    }

    // 프로젝트 루트의 ' (2).env' 또는 '(2).env' 파일 탐색
    let envPath = path.join(__dirname, ' (2).env');
    if (!fs.existsSync(envPath)) {
        envPath = path.join(__dirname, '(2).env');
    }

    if (!fs.existsSync(envPath)) {
        console.error(`환경변수 파일을 찾을 수 없습니다: ${envPath}`);
        process.exit(1);
    }

    const envContent = fs.readFileSync(envPath, 'utf8');
    const restApiKeyMatch = envContent.match(/KAKAO_REST_API_KEY\s*=\s*(.+)/);
    const clientSecretMatch = envContent.match(/KAKAO_CLIENT_SECRET\s*=\s*(.+)/);

    if (!restApiKeyMatch) {
        console.error('KAKAO_REST_API_KEY 항목을 찾을 수 없습니다.');
        process.exit(1);
    }

    const clientId = restApiKeyMatch[1].trim();
    const clientSecret = clientSecretMatch ? clientSecretMatch[1].trim() : '';
    const redirectUri = 'http://localhost';

    console.log(`[정보] REST API 키: ${clientId}`);
    console.log(`[정보] 리다이렉트 URI: ${redirectUri}`);
    console.log(`[정보] 인가코드: ${authCode.trim()}`);

    const params = new URLSearchParams();
    params.append('grant_type', 'authorization_code');
    params.append('client_id', clientId);
    params.append('redirect_uri', redirectUri);
    params.append('code', authCode.trim());
    if (clientSecret) {
        params.append('client_secret', clientSecret);
    }

    try {
        const response = await fetch('https://kauth.kakao.com/oauth/token', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded;charset=utf-8'
            },
            body: params.toString()
        });

        const data = await response.json();

        if (!response.ok) {
            console.error('[오류 발생]', data);
            return;
        }

        const refreshToken = data.refresh_token;
        console.log('[성공] 리프레시 토큰 발급 완료:', refreshToken);

        // env 파일 업데이트
        let lines = envContent.split(/\r?\n/);
        let found = false;
        lines = lines.map(line => {
            if (line.startsWith('KAKAO_REFRESH_TOKEN=')) {
                found = true;
                return `KAKAO_REFRESH_TOKEN=${refreshToken}`;
            }
            return line;
        });

        if (!found) {
            // 끝에 빈 줄이 없으면 추가 후 삽입
            if (lines.length > 0 && lines[lines.length - 1].trim() !== '') {
                lines.push('');
            }
            lines.push(`KAKAO_REFRESH_TOKEN=${refreshToken}`);
        }

        fs.writeFileSync(envPath, lines.join('\n').trim() + '\n', 'utf8');
        console.log(`[완료] ${envPath} 파일에 KAKAO_REFRESH_TOKEN 저장을 완료했습니다.`);
    } catch (err) {
        console.error('[네트워크/요청 오류]:', err);
    }
}

const authCode = process.argv[2];
getKakaoToken(authCode);
