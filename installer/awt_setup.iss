; Inno Setup 6 스크립트 — AWT v1.0 Windows 인스톨러 (원클릭 설치)
; 빌드: ISCC.exe installer\awt_setup.iss

#define AppName "AWT"
#define AppVersion "1.0.0"
#define AppPublisher "TTA SW 시험인증팀"
#define AppExeName "AWT.exe"
#define DistDir "..\dist\AWT"

[Setup]
AppId={{A3B2C1D0-E4F5-4A6B-8C7D-9E0F1A2B3C4D}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL=https://github.com/TTAJihoon/AutoWebTesting
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
OutputDir=..\dist\installer
OutputBaseFilename=AWT_Setup_{#AppVersion}
; SetupIconFile=awt.ico   ; 아이콘 파일 있을 때 활성화
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
MinVersion=10.0.17763

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon"; Description: "바탕화면 바로가기 생성"; GroupDescription: "추가 아이콘:"; Flags: checked

[Files]
; PyInstaller COLLECT 출력 전체 포함 (.env 제외 — 아래 [Code]에서 생성)
Source: "{#DistDir}\*"; DestDir: "{app}"; \
  Excludes: ".env"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#DistDir}\.env.example"; DestDir: "{app}"; \
  Flags: ignoreversion; DestName: ".env.example"

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\{#AppName} 제거"; Filename: "{uninstallexe}"
Name: "{commondesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; \
  Description: "AWT 실행"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; ~/.awt (API Key 암호화 저장소)는 보존, 앱 디렉터리만 제거
Type: filesandordirs; Name: "{app}"

; ─────────────────────────────────────────────────────────────────────────────
[Code]
{ 커스텀 설치 페이지: DB 연결 정보 + LLM API Key 입력 }

var
  DBPage: TInputQueryWizardPage;
  APIPage: TInputQueryWizardPage;

procedure InitializeWizard;
begin
  // ── 페이지 1: DB 연결 정보 ───────────────────────────────────────────
  DBPage := CreateInputQueryPage(
    wpSelectDir,
    'PostgreSQL DB 연결 설정',
    'AWT 계정/세션 관리에 사용할 PostgreSQL 서버 정보를 입력하세요.',
    ''
  );
  DBPage.Add('DB 호스트 (예: 210.96.71.241):', False);
  DBPage.Add('포트 (기본: 5432):', False);
  DBPage.Add('DB 이름 (기본: awt):', False);
  DBPage.Add('DB 사용자 (기본: awt_user):', False);
  DBPage.Add('DB 비밀번호:', True);   // True = 비밀번호 마스킹

  DBPage.Values[0] := '210.96.71.241';
  DBPage.Values[1] := '5432';
  DBPage.Values[2] := 'awt';
  DBPage.Values[3] := 'awt_user';
  DBPage.Values[4] := '';

  // ── 페이지 2: LLM API Key ────────────────────────────────────────────
  APIPage := CreateInputQueryPage(
    DBPage.ID,
    'LLM API Key 설정',
    '사용할 LLM 공급사의 API Key를 입력하세요. (하나 이상 입력 권장)',
    '입력한 Key는 설치 PC에 암호화 저장됩니다. 나중에 앱 설정 탭에서도 변경 가능합니다.'
  );
  APIPage.Add('Google Gemini API Key (AIza...):', True);
  APIPage.Add('Anthropic Claude API Key (sk-ant-...):', True);
  APIPage.Add('OpenAI API Key (sk-...):', True);

  APIPage.Values[0] := '';
  APIPage.Values[1] := '';
  APIPage.Values[2] := '';
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Host, Port, DbName, DbUser, DbPw: String;
begin
  Result := True;

  // DB 페이지 유효성 검사
  if CurPageID = DBPage.ID then
  begin
    Host   := Trim(DBPage.Values[0]);
    Port   := Trim(DBPage.Values[1]);
    DbName := Trim(DBPage.Values[2]);
    DbUser := Trim(DBPage.Values[3]);
    DbPw   := DBPage.Values[4];

    if Host = '' then begin
      MsgBox('DB 호스트를 입력하세요.', mbError, MB_OK);
      Result := False; Exit;
    end;
    if DbPw = '' then begin
      MsgBox('DB 비밀번호를 입력하세요.', mbError, MB_OK);
      Result := False; Exit;
    end;
  end;

  // API Key 페이지: 하나도 없으면 경고 (차단하지는 않음)
  if CurPageID = APIPage.ID then
  begin
    if (Trim(APIPage.Values[0]) = '') and
       (Trim(APIPage.Values[1]) = '') and
       (Trim(APIPage.Values[2]) = '') then
    begin
      if MsgBox('API Key가 입력되지 않았습니다. 나중에 앱 설정 탭에서 입력할 수 있습니다. 계속하시겠습니까?',
                mbConfirmation, MB_YESNO) = IDNO then
      begin
        Result := False; Exit;
      end;
    end;
  end;
end;

procedure WriteEnvFile(EnvPath: String);
var
  Lines: TArrayOfString;
  Provider: String;
  GoogleKey, AnthropicKey, OpenAIKey: String;
begin
  GoogleKey    := Trim(APIPage.Values[0]);
  AnthropicKey := Trim(APIPage.Values[1]);
  OpenAIKey    := Trim(APIPage.Values[2]);

  // Provider 자동 결정 (입력된 키 중 첫 번째)
  if GoogleKey <> '' then Provider := 'google'
  else if AnthropicKey <> '' then Provider := 'anthropic'
  else if OpenAIKey <> '' then Provider := 'openai'
  else Provider := 'google';

  SetArrayLength(Lines, 14);
  Lines[0]  := '# AWT 설정 파일 — 설치 마법사로 생성됨';
  Lines[1]  := '';
  Lines[2]  := '# LLM Provider';
  Lines[3]  := 'LLM_PROVIDER=' + Provider;
  Lines[4]  := '';
  Lines[5]  := '# API Keys';
  if GoogleKey <> '' then
    Lines[6] := 'GOOGLE_API_KEY=' + GoogleKey
  else
    Lines[6] := '# GOOGLE_API_KEY=';
  if AnthropicKey <> '' then
    Lines[7] := 'ANTHROPIC_API_KEY=' + AnthropicKey
  else
    Lines[7] := '# ANTHROPIC_API_KEY=';
  if OpenAIKey <> '' then
    Lines[8] := 'OPENAI_API_KEY=' + OpenAIKey
  else
    Lines[8] := '# OPENAI_API_KEY=';
  Lines[9]  := '';
  Lines[10] := '# PostgreSQL AWT DB';
  Lines[11] := 'AWT_DB_HOST=' + Trim(DBPage.Values[0]);
  Lines[12] := 'AWT_DB_PORT=' + Trim(DBPage.Values[1]);
  Lines[13] := 'AWT_DB_NAME=' + Trim(DBPage.Values[2]);
  SaveStringsToFile(EnvPath, Lines, False);

  // 비밀번호/사용자는 별도 append (SaveStringsToFile로는 개행 처리 어려움)
  SaveStringToFile(EnvPath, 'AWT_DB_USER=' + Trim(DBPage.Values[3]) + #13#10, True);
  SaveStringToFile(EnvPath, 'AWT_DB_PASSWORD=' + DBPage.Values[4] + #13#10, True);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // .env 파일을 설치 디렉터리에 생성
    WriteEnvFile(ExpandConstant('{app}\.env'));
  end;
end;
