# التشغيل الدائم (macOS + launchd)

TUC مصمم ليعمل على جهاز Mac شخصي أو Mac mini كخادم منزلي، بدون Docker.

## 1. التثبيت

```bash
./scripts/install_macos.sh                 # آمن للتكرار
mysql -u root < scripts/setup_mysql.sql    # غيّر كلمة المرور في الملف وفي .env
uv sync
cp .env.example .env && chmod 600 .env
```

عدّل `.env`: قاعدة البيانات، بيانات تليجرام، `TUC_SESSION_SECRET`، و `DASHBOARD_PASSWORD`
(يُفضّل hash من `uv run python -m app.cli hash-password`). اجعل `TUC_APP_ENV=production` إن كان الوصول عبر HTTPS.

```bash
uv run python -m app.cli init-db
uv run python -m app.cli telegram-login
uv run python -m app.cli health-check
cd frontend && npm install && npm run build && cd ..
```

## 2. مهام launchd

```bash
uv run python -m app.cli launchd install          # --port 8000 --host 127.0.0.1
uv run python -m app.cli launchd status
```

الأمر يولّد ثلاث LaunchAgents من القوالب في `deploy/launchd/` بمسارات مطلقة (الـ venv والمشروع، حتى لو فيها
مسافات)، ينسخها إلى `~/Library/LaunchAgents/`، ويحمّلها بـ `launchctl bootstrap gui/$(id -u)`:

| Label | ماذا يفعل | التوقيت |
|---|---|---|
| `com.tuc.web` | `serve` — لوحة التحكم | `RunAtLoad` + `KeepAlive` (يُعاد تشغيله إن توقف) |
| `com.tuc.collector` | `collect --trigger launchd` | كل `TUC_COLLECT_INTERVAL_MINUTES` (StartInterval) |
| `com.tuc.process` | `process --trigger launchd` | كل `TUC_PROCESS_INTERVAL_MINUTES` |

السجلات: `~/Library/Logs/tuc/*.out.log` و `*.err.log`، وسجل كل تشغيل بصيغة JSON في `logs/runs/<id>.jsonl`
ويظهر في صفحة «التشغيلات».

### السكون والتداخل

- إن كان الجهاز نائماً وقت موعد مهمة، **يشغّلها launchd مرة واحدة عند الاستيقاظ** (لا تتراكم).
- **القفل** (`storage/collector.lock` بـ `fcntl.flock`) يمنع تشغيل collect و process معاً، سواء بدأت من launchd
  أو من لوحة التحكم أو من الطرفية. المهمة الثانية تخرج بالكود 75 بهدوء وتُعاد في موعدها التالي.
- إن توقفت عملية فجأة، النظام يحرر القفل تلقائياً، والتشغيل «العالق» يُعلَّم `aborted` في المرة التالية.

### التحديث

```bash
git pull
uv sync
uv run python -m app.cli init-db --no-import-config     # migrations جديدة إن وُجدت
cd frontend && npm install && npm run build && cd ..
uv run python -m app.cli launchd install                # يعيد التحميل
```

### الإزالة

```bash
uv run python -m app.cli launchd uninstall
```

## 3. النسخ الاحتياطي

- قاعدة البيانات: `mysqldump --single-transaction --default-character-set=utf8mb4 -u tuc -p tuc > tuc-$(date +%F).sql`
- الملفات: مجلد `storage/` (يحتوي أيضاً جلسة تليجرام — احفظه بشكل آمن).
- الإعدادات: `.env` و `uv run python -m app.cli export-config`.

## 4. الوصول من أجهزة أخرى

الخادم يستمع على `127.0.0.1` فقط افتراضياً. للوصول من الشبكة استخدم reverse proxy بـ HTTPS
(مثال nginx في `deploy/nginx/tuc.conf`) مع `TUC_APP_ENV=production`، ولا تفتح المنفذ مباشرة بـ `--host 0.0.0.0`.

## 5. اختياري: خادم Linux

إن نُقل المشروع لخادم Linux، توجد ملفات systemd في `deploy/linux/`:
`tuc-web.service` و `tuc-collector.service/.timer` و `tuc-process.service/.timer`
(كلها `After=mysql.service`، و `SuccessExitStatus=75` لمهام الجمع والمعالجة)، مع إعداد nginx في `deploy/nginx/`.

```bash
sudo cp deploy/linux/* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tuc-web tuc-collector.timer tuc-process.timer
```
