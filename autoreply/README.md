# الرد الآلي على تعليقات إنستقرام

بديل Metricool Flows. يعمل كل ١٥ دقيقة من GitHub Actions عبر واجهة Meta الرسمية (private replies).

- `replies.json`: الكلمات المفتاحية ونص الرسالة الخاصة والرد العام. يُرسل فقط ما فيه `"enabled": true`.
- `ig_autoreply.py`: يقرأ تعليقات آخر ٢٥ منشوراً، يرسل رسالة خاصة واحدة لكل تعليق مطابق ثم يرد علناً. الرد العام هو علامة المعالجة، فلا يتكرر الإرسال.

## التشغيل
1. Settings ← Secrets and variables ← Actions ← Secrets: `IG_ACCESS_TOKEN` (توكن إنستقرام طويل الأجل بصلاحيات `instagram_business_basic` و`instagram_business_manage_comments` و`instagram_business_manage_messages`).
2. بدون أي إعداد آخر يعمل بوضع التجربة: يطبع في سجل Actions ما كان سيرسله ولا يرسل شيئاً.
3. للإرسال الفعلي: Variables ← `IG_AUTOREPLY_LIVE` = `true`.

التوكن صالح ٦٠ يوماً ويحتاج تجديداً قبل انتهائه. لا تضع التوكن في أي ملف.
