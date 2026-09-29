# TUC — جامع المحتوى الجامعي من تليجرام

نظام يجمع ملفات المواد الدراسية (PDF، صور، Word، PowerPoint) من قنوات تليجرام تختارها، ويمنع التكرار،
ويستخرج النص (مع OCR للعربية والإنجليزية)، ويصنّف كل ملف حسب **المادة** و**نوع المحتوى**، ثم ينظّمه في
مجلدات مرتبة، مع لوحة تحكم ويب ثنائية اللغة لإدارة كل شيء ومتابعته لحظياً.

يعمل مباشرة على **macOS (Apple Silicon و Intel)** — بدون Docker وبدون Redis/Celery.
MySQL 8 و Tesseract عبر Homebrew، وبايثون داخل venv عبر `uv`، والجدولة عبر **launchd**.

مستندات أخرى: [CONFIGURATION_AR.md](CONFIGURATION_AR.md) · [TROUBLESHOOTING_AR.md](TROUBLESHOOTING_AR.md) ·
[DEPLOYMENT_AR.md](DEPLOYMENT_AR.md) · [README.md](README.md) (English)

## كيف يعمل

```
قنوات تليجرام ──► collect ──► storage/incoming ──► process ──► storage/processed/<المادة>/<النوع>/
 (المفعّلة فقط)     │ فحص تكرار بـ document.id        │ استخراج النص (نص PDF ← OCR عند الحاجة)
                   │ ثم SHA-256 بعد التحميل          │ قواعد كلمات مفتاحية ← OpenAI (اختياري)
                   └ FloodWait + تحديد المعدّل        └ storage/unclassified/ عند عدم اليقين
```

- **الجمع**: يقرأ القنوات المفعّلة فقط من الأقدم للأحدث بدءاً من `last_message_id`، ويحدّثه **بعد كل رسالة
  تنجح معالجتها** — فلا يضيع شيء ولا يتكرر عند أي انقطاع. التحميل ذرّي (`.part` ثم rename) ومحصور داخل
  مجلد التخزين، وأسماء الملفات العربية تُوحّد بـ NFC.
- **المعالجة**: نص PDF المدمج أولاً، وإن كان أقل من `TUC_MIN_PDF_TEXT_CHARS` يُستخدم OCR لأول
  `TUC_OCR_MAX_PAGES` صفحة. الصور بـ OCR، و docx/pptx بمكتباتها. النص يُنظّف ويُطبّع عربياً ويُحفظ في
  `storage/texts/<id>.txt` بصلاحيات 600.
- **التصنيف الصارم**: القواعد أولاً (`rules-v1`)، ثم OpenAI فقط لما لم تحسمه القواعد، ثم تحقق صارم:
  المادة موجودة في قاعدة البيانات، والنوع من القائمة الثابتة، والثقة والأدلة فوق الحد. أي فشل ← `unclassified`
  مع سبب واضح. **لا يخترع النظام مواد أو أنواعاً أبداً.**

أنواع المحتوى الثابتة: `lecture` محاضرة، `previous_exam` امتحان سابق، `assignment` تكليف،
`answer_model` نموذج إجابة، `summary` ملخص.

> **مهم:** التصنيف يحتاج **مواد معرّفة** (من صفحة المواد أو `config/subjects.yaml`).
> **تصنيف القواعد يعمل بدون أي مفتاح**، أما **التصنيف الذكي** فيحتاج مفتاح OpenAI (`TUC_AI_PROVIDER=openai`).

## التشغيل المحلي

```bash
./scripts/install_macos.sh
mysql -u root < scripts/setup_mysql.sql
uv sync
cp .env.example .env && chmod 600 .env        # ثم عدّل القيم
uv run python -m app.cli health-check
uv run python -m app.cli init-db
uv run python -m app.cli seed-demo             # اختياري: بيانات تجريبية
cd frontend && npm install && npm run build && cd ..
uv run python -m app.cli serve --host 127.0.0.1 --port 8000
```

افتح <http://127.0.0.1:8000> وادخل بـ `DASHBOARD_USERNAME` / `DASHBOARD_PASSWORD`.

للتشغيل التلقائي في الخلفية (لوحة التحكم + الجمع + المعالجة):

```bash
uv run python -m app.cli launchd install      # أو uninstall / status
```

## قبل التشغيل الحقيقي

1. **بيانات Telegram API** من <https://my.telegram.org> ← API development tools، وضعها في
   `TUC_TELEGRAM_API_ID` و `TUC_TELEGRAM_API_HASH`.
2. **تسجيل الدخول لتليجرام:** `uv run python -m app.cli telegram-login` (رقم الهاتف ← الكود ← كلمة مرور
   التحقق بخطوتين إن وُجدت). ملف الجلسة يُنشأ بصلاحيات 600.
3. **الحساب يجب أن يكون عضواً** في كل قناة تضيفها.
4. **MySQL شغال**: `brew services list`.
5. **Tesseract مع لغتي ara و eng**: `tesseract --list-langs`.
6. **مفتاح OpenAI** إن أردت التصنيف الذكي (اختياري).

## أوامر سطر الأوامر

كلها بصيغة `uv run python -m app.cli <الأمر>`:

| الأمر | الوظيفة |
|---|---|
| `health-check` | فحص MySQL و utf8mb4 و Tesseract ولغاته وجلسة تليجرام و OpenAI والتخزين والصلاحيات و launchd |
| `init-db` | تطبيق الـ migrations وإنشاء مجلدات التخزين واستيراد YAML أول مرة |
| `telegram-login` | تسجيل دخول تليجرام تفاعلياً |
| `collect [--channel X] [--limit N]` | جمع الملفات الجديدة |
| `process [--limit N]` | استخراج النص والتصنيف والنقل |
| `reclassify [--status unclassified]` | إعادة التصنيف من النص المحفوظ (مفيد بعد إضافة مادة) |
| `report [--json]` | تقرير: الإجمالي، حسب المادة والنوع، والمواد بلا محتوى |
| `import-config` / `export-config` | استيراد/تصدير المواد والقنوات بصيغة YAML |
| `serve` | تشغيل لوحة التحكم والـ API |
| `seed-demo [--reset]` | بيانات تجريبية |
| `hash-password` | توليد hash بـ argon2 لكلمة مرور لوحة التحكم |
| `launchd install / uninstall / status` | إدارة المهام الخلفية |

عند وجود مهمة أخرى شغالة يخرج الأمر بالكود **75** مع رسالة واضحة (القفل مشترك بين سطر الأوامر ولوحة
التحكم و launchd).

## لوحة التحكم

- **نظرة عامة**: مؤشرات رئيسية مع sparkline ونسبة التغيير، ورسم يومي لآخر 30 يوماً، والتوزيع حسب النوع
  والمادة، وتنبيه المواد بلا محتوى، وآخر الملفات وآخر تشغيل، وصحة النظام.
- **الجمع المباشر**: زرّا جمع ومعالجة، مع بث حي للـ logs عبر Server-Sent Events وعدّادات لحظية. الأزرار
  تُعطّل تلقائياً إن كانت هناك مهمة شغالة من أي مصدر.
- **القنوات / المواد / الملفات / الرسائل / التشغيلات / الإعدادات**.
- العربية افتراضية بـ RTL كامل، مع وضع فاتح وداكن، و ⌘K / Ctrl+K لفتح لوحة الأوامر.

## الاختبارات

```bash
uv run ruff check . && uv run mypy app tests && uv run pytest
cd frontend && npm test -- --run && E2E_PASSWORD=... npm run e2e
```

الاختبارات تعمل على قاعدة MySQL منفصلة (`TUC_TEST_DATABASE_URL`) و**ترفض العمل إن لم ينتهِ اسمها بـ `_test`**.
اختبارات OCR تُتخطى تلقائياً مع رسالة إن لم يكن Tesseract أو لغاته مثبتة.
