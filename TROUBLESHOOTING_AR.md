# حل المشكلات

ابدأ دائماً بـ:

```bash
uv run python -m app.cli health-check
```

## MySQL لا يعمل

العرض: `Cannot connect` في health-check، أو `db: unreachable` في `/healthz`، أو مؤشر MySQL أحمر في القائمة.

```bash
brew services list                 # هل mysql بحالة started؟
brew services restart mysql
mysqladmin ping                    # يجب أن يطبع: mysqld is alive
tail -50 "$(brew --prefix)/var/mysql/$(hostname).err"
```

- **Access denied**: تأكد أن المستخدم وكلمة المرور في `TUC_DATABASE_URL` مطابقان لـ `scripts/setup_mysql.sql`،
  وأعد تشغيل السكربت (آمن للتكرار): `mysql -u root < scripts/setup_mysql.sql`.
- **charset ليس utf8mb4**: السكربت يصلح ذلك بـ `ALTER DATABASE`. الجداول تُنشأ بـ utf8mb4 عبر `init-db`.
- **Unknown database**: شغّل `setup_mysql.sql` ثم `init-db`.

## tesseract غير موجود أو لغة ara ناقصة

```bash
brew install tesseract tesseract-lang
tesseract --list-langs             # يجب أن تظهر ara و eng
```

- إن ظهرت eng فقط: `brew reinstall tesseract-lang`.
- إن كان tesseract في مسار غير معتاد: ضع المسار الكامل في `TUC_TESSERACT_CMD`.
- بدون OCR تبقى ملفات PDF النصية و docx/pptx تعمل؛ الصور و PDF الممسوحة فقط تحتاجه.
- إن فشل تنزيل Homebrew بسبب الشبكة (`Failed to download ... ghcr.io`) أعد المحاولة، أو
  `HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_CURL_RETRIES=8 brew install tesseract-lang`.

## صلاحيات macOS (Full Disk Access)

إن جعلت `TUC_STORAGE_ROOT` خارج مجلد المستخدم (قرص خارجي، `/Volumes/...`) أو داخل Desktop/Documents/Downloads،
قد يمنع macOS مهام launchd من الوصول (خطأ `Operation not permitted`) رغم أنها تعمل من الطرفية.

الحل: System Settings ← Privacy & Security ← **Full Disk Access** ← أضف:
- ملف بايثون الموجود في `.venv/bin/python` داخل المشروع (اضغط ⌘⇧G والصق المسار، والرابط الرمزي يشير
  لبايثون الحقيقي، فأضفه أيضاً إن لزم: `readlink -f .venv/bin/python`).
- وتطبيق Terminal إن كنت تشغّل من الطرفية.

ثم أعد تحميل المهام: `uv run python -m app.cli launchd install`.

> ملاحظة: إن كان المشروع نفسه داخل Desktop أو Documents فقد تحتاج الإذن للمهام الخلفية أيضاً.
> المكان الأسهل هو مجلد مثل `~/tuc`.

## مهام launchd لا تعمل

```bash
uv run python -m app.cli launchd status
launchctl print gui/$(id -u)/com.tuc.collector      # الحالة وآخر exit code
tail -50 ~/Library/Logs/tuc/collector.err.log
```

- **last exit code = 75**: هذا طبيعي؛ يعني أن مهمة أخرى كانت شغالة وقتها (القفل منع التداخل).
- **last exit code = 2**: بيانات تليجرام ناقصة أو الجلسة غير مسجلة ← `telegram-login`.
- **المهمة غير موجودة**: `launchd install` مرة أخرى (يعمل bootout ثم bootstrap).
- **الـ venv غير موجود**: الـ plists تشير لمسار `.venv/bin/python` المطلق؛ إن نقلت المشروع أو حذفت `.venv`
  شغّل `uv sync` ثم `launchd install`.
- **تشغيل يدوي فوري**: `launchctl kickstart -k gui/$(id -u)/com.tuc.collector`.
- **المنفذ مشغول** (web): غيّر المنفذ `launchd install --port 8010`.

launchd يشغّل المهام الفائتة مرة واحدة عند استيقاظ الجهاز من السكون (StartInterval)، والقفل يضمن عدم تداخل
الجمع والمعالجة.

## FloodWait من تليجرام

تليجرام يطلب الانتظار عند كثرة الطلبات. الجامع ينتظر المدة المطلوبة تلقائياً ثم يكمل من آخر رسالة ناجحة،
وتظهر في السجل كـ `flood_wait seconds=...`.

- إن كانت المدة أطول من `TUC_TELEGRAM_FLOOD_MAX_WAIT_SECONDS` (افتراضي 900) تتوقف القناة بحالة «خطأ»
  وتُستأنف في التشغيل التالي من نفس النقطة.
- لتقليل حدوثه: زد `TUC_TELEGRAM_REQUEST_DELAY_SECONDS` (مثلاً 2)، واستخدم `--limit` في أول جمع للقنوات الكبيرة،
  وزد `TUC_COLLECT_INTERVAL_MINUTES`.

## مشاكل أخرى شائعة

| العرض | السبب والحل |
|---|---|
| `Telegram session is not authorized` | شغّل `telegram-login` |
| `Cannot access channel` | الحساب ليس عضواً، أو المعرّف خاطئ، أو القناة خاصة ← استخدم `telegram_id` |
| كل الملفات `unclassified` | لا توجد مواد، أو كلماتها المفتاحية قليلة، أو `TUC_AI_PROVIDER=none`. أضف مواد/كلمات ثم `reclassify` |
| ملف `failed` بـ `PDF is password protected` | ملف محمي؛ لا يمكن استخراجه |
| `.doc` / `.ppt` = unsupported | صيغ Office القديمة غير مدعومة؛ حوّلها لـ docx/pptx/PDF |
| الجلسات تنتهي عند كل إعادة تشغيل | `TUC_SESSION_SECRET` غير مضبوط |
| `429 Too many attempts` عند الدخول | انتظر 5 دقائق (حماية من التخمين) |
| لوحة التحكم تعرض «not built yet» | `cd frontend && npm install && npm run build` |
| رسالة «هناك مهمة قيد التشغيل» لا تختفي | `health-check` يعرض صاحب القفل (pid). القفل يُحرَّر تلقائياً إن توقفت العملية |
