# الإعدادات

كل الإعدادات في ملف `.env` بجذر المشروع (انسخه من `.env.example`، واجعل صلاحياته `chmod 600 .env`).
المسارات النسبية تُحسب من مجلد المشروع، لذلك تعمل بنفس الشكل من سطر الأوامر ولوحة التحكم و launchd.
بعد أي تعديل أعد تشغيل الخادم (أو `launchctl kickstart -k gui/$(id -u)/com.tuc.web`).

## قاعدة البيانات هي مصدر الحقيقة

القنوات والمواد تُدار من لوحة التحكم وتُحفظ في MySQL. ملفا `config/subjects.yaml` و `config/channels.yaml`
للاستيراد الأولي فقط (`init-db` يستوردهما إن كانت القاعدة فارغة)، ويمكن الاستيراد/التصدير في أي وقت:

```bash
uv run python -m app.cli import-config            # upsert: يضيف الجديد ويحدّث الموجود
uv run python -m app.cli export-config --out-dir config/export
```

### subjects.yaml

```yaml
subjects:
  - code: DB101                    # فريد، حروف/أرقام/-/_ ، ويُستخدم كاسم مجلد
    name_ar: "قواعد البيانات"
    name_en: "Database"
    keywords: ["database", "sql", "قواعد بيانات", "ERD"]
```

نصائح للكلمات المفتاحية: أضف الاختصارات التي يكتبها الطلاب (`DB`, `داتابيز`)، والمصطلحات المميزة للمادة.
المطابقة تتجاهل الهمزات والتشكيل والتطويل و ى/ي و ة/ه وحالة الأحرف.

### channels.yaml

```yaml
channels:
  - name: "دفعة علوم الحاسب"
    username: "cs_batch_2026"       # المعرّف العام بدون @
    enabled: true
  - name: "مجموعة خاصة"
    telegram_id: -1001234567890     # للقنوات الخاصة
```

## المتغيرات

### التطبيق
| المتغير | الافتراضي | الوصف |
|---|---|---|
| `TUC_APP_ENV` | `development` | `production` يفعّل الكوكي Secure و HSTS ويُلزم بـ `TUC_SESSION_SECRET` |
| `TUC_LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `TUC_LOG_FORMAT` | `auto` | `auto` = JSON في الإنتاج ومقروء في التطوير |
| `TUC_LOG_DIR` | `logs` | فيه `runs/<id>.jsonl` لكل تشغيل |

### قاعدة البيانات
| المتغير | الوصف |
|---|---|
| `TUC_DATABASE_URL` | `mysql+pymysql://tuc:PASS@127.0.0.1:3306/tuc?charset=utf8mb4` |
| `TUC_TEST_DATABASE_URL` | قاعدة الاختبارات — **يجب أن ينتهي اسمها بـ `_test`** |

### تليجرام
| المتغير | الافتراضي | الوصف |
|---|---|---|
| `TUC_TELEGRAM_API_ID` / `TUC_TELEGRAM_API_HASH` | — | من my.telegram.org |
| `TUC_TELEGRAM_SESSION_PATH` | `storage/telegram/tuc` | يُضاف له `.session` تلقائياً |
| `TUC_TELEGRAM_REQUEST_DELAY_SECONDS` | `1.0` | أقل فاصل بين الطلبات (يقلل FloodWait) |
| `TUC_TELEGRAM_COLLECT_TEXT_MESSAGES` | `false` | حفظ الرسائل النصية بدون ملفات أيضاً |

### التخزين
| المتغير | الافتراضي |
|---|---|
| `TUC_STORAGE_ROOT` | `storage` |
| `TUC_INCOMING_STORAGE_DIR` | `storage/incoming` |
| `TUC_PROCESSED_STORAGE_DIR` | `storage/processed` — `<المادة>/<النوع>/<id>_<الاسم>` |
| `TUC_UNCLASSIFIED_STORAGE_DIR` | `storage/unclassified` |
| `TUC_TEXTS_STORAGE_DIR` | `storage/texts` (صلاحيات 700، والملفات 600) |
| `TUC_LOCK_FILE_PATH` | `storage/collector.lock` |

إن وضعت التخزين خارج مجلد المستخدم (قرص خارجي مثلاً) راجع قسم Full Disk Access في
[TROUBLESHOOTING_AR.md](TROUBLESHOOTING_AR.md).

### OCR
| المتغير | الافتراضي | الوصف |
|---|---|---|
| `TUC_OCR_ENABLED` | `true` | |
| `TUC_OCR_LANGUAGE` | `ara+eng` | |
| `TUC_OCR_MAX_PAGES` | `15` | حد صفحات OCR للـ PDF الممسوح |
| `TUC_TESSERACT_CMD` | فارغ | فارغ = اكتشاف تلقائي: PATH ثم `/opt/homebrew/bin` ثم `/usr/local/bin` |
| `TUC_MIN_PDF_TEXT_CHARS` | `200` | أقل من هذا ← يُستخدم OCR |

### التصنيف
| المتغير | الافتراضي | الوصف |
|---|---|---|
| `TUC_AI_PROVIDER` | `none` | `openai` لتفعيل التصنيف الذكي لما لا تحسمه القواعد |
| `TUC_OPENAI_API_KEY` | — | |
| `TUC_OPENAI_MODEL` | `gpt-4.1-mini` | أي نموذج يدعم Structured Outputs |
| `TUC_MAX_CLASSIFICATION_CHARS` | `6000` | أول N حرف من النص تُرسل |
| `TUC_CLASSIFICATION_MIN_CONFIDENCE` | `0.7` | أقل ثقة مقبولة |
| `TUC_CLASSIFICATION_MIN_EVIDENCE_ITEMS` | `1` | أقل عدد أدلة مقبول |

إذا كان `TUC_AI_PROVIDER=none` ولم تحسم القواعد الملف، يصبح `unclassified` بالسبب
`AI provider is disabled`. بعد إضافة مواد أو تفعيل OpenAI شغّل `reclassify`.

### الجدولة (launchd)
| المتغير | الافتراضي |
|---|---|
| `TUC_COLLECT_INTERVAL_MINUTES` | `30` |
| `TUC_PROCESS_INTERVAL_MINUTES` | `15` |

بعد تغييرها أعد `launchd install` لتوليد الـ plists من جديد.

### لوحة التحكم
| المتغير | الوصف |
|---|---|
| `TUC_SESSION_SECRET` | سر توقيع الكوكي: `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `DASHBOARD_USERNAME` | اسم المستخدم (افتراضي `admin`) |
| `DASHBOARD_PASSWORD` | يُفضّل hash بـ argon2 من `uv run python -m app.cli hash-password` (ضعه بين علامتي تنصيص مفردة). كلمة مرور عادية تعمل أيضاً لكنها تُحوّل لـ hash في الذاكرة ولا تُخزّن |

صفحة الإعدادات في لوحة التحكم تعرض كل هذه القيم للقراءة فقط، والقيم السرية تظهر فقط كـ «مُعَدّ ✓» أو «غير مُعَدّ».
