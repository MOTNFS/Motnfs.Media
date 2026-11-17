#!/usr/bin/env python3
"""متنفس | الرد الآلي على تعليقات إنستقرام (بديل Metricool Flows).

يعمل عبر واجهة Meta الرسمية فقط (Instagram API with Instagram Login):
  1. يقرأ تعليقات آخر المنشورات.
  2. إذا احتوى التعليق كلمة مفتاحية من replies.json يرسل رسالة خاصة واحدة
     (private reply) ثم يرد رداً عاماً تحت التعليق.
  3. الرد العام هو علامة «تمت المعالجة»: أي تعليق تحته رد من حسابنا لا يُعالج
     مرة ثانية، فلا نحتاج قاعدة بيانات.

المتغيرات:
  IG_ACCESS_TOKEN     توكن إنستقرام طويل الأجل (إلزامي، من أسرار المستودع).
  IG_AUTOREPLY_LIVE   "true" للإرسال الفعلي. غير ذلك = تجربة بلا إرسال.
  IG_API_BASE         افتراضي https://graph.instagram.com
  IG_MEDIA_LIMIT      عدد آخر المنشورات المفحوصة (افتراضي 25).
"""
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = os.environ.get("IG_API_BASE", "https://graph.instagram.com").rstrip("/")
TOKEN = os.environ.get("IG_ACCESS_TOKEN", "").strip()
LIVE = os.environ.get("IG_AUTOREPLY_LIVE", "").strip().lower() == "true"
MEDIA_LIMIT = int(os.environ.get("IG_MEDIA_LIMIT", "25"))
COMMENT_MAX_AGE = timedelta(days=6, hours=20)  # نافذة Meta للرد الخاص ٧ أيام
MAX_SENDS_PER_RUN = 40
CONFIG = Path(__file__).with_name("replies.json")

_DIACRITICS = re.compile(r"[ؐ-ًؚ-ٰٟـ]")
_NON_WORD = re.compile(r"[^\w\s]", re.UNICODE)


def normalize(text):
    """توحيد الكتابة العربية حتى تطابق «الإتزان» و«اتزان» و«الاتزان»."""
    t = _DIACRITICS.sub("", text or "")
    t = re.sub("[أإآٱ]", "ا", t)
    t = t.replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي")
    t = _NON_WORD.sub(" ", t).lower()
    return " ".join(t.split())


def match_reply(comment_text, replies):
    """أول رد مفعّل تظهر إحدى كلماته ككلمة مستقلة في التعليق (مع «ال» أو بدونها)."""
    words = set(normalize(comment_text).split())
    words |= {w[2:] for w in words if w.startswith("ال") and len(w) > 4}
    for r in replies:
        if not r.get("enabled"):
            continue
        for kw in r.get("keywords", []):
            k = normalize(kw)
            if k in words or (k.startswith("ال") and k[2:] in words):
                return r
    return None


def api(method, path, params=None, body=None):
    url = f"{BASE}/{path.lstrip('/')}"
    q = dict(params or {})
    q["access_token"] = TOKEN
    url += "?" + urllib.parse.urlencode(q)
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            err = json.loads(raw).get("error", {})
            msg = f"{err.get('code')}/{err.get('error_subcode')}: {err.get('message')}"
        except Exception:
            msg = raw[:300]
        raise RuntimeError(f"HTTP {e.code} {msg}".replace(TOKEN, "***")) from None


def parse_ts(ts):
    # مثال: 2026-11-17T12:00:00+0000
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S%z")


def already_handled(comment, me_username):
    for rep in (comment.get("replies") or {}).get("data", []):
        if (rep.get("username") or "").lower() == me_username:
            return True
    return False


def main():
    if not TOKEN:
        print("لا يوجد IG_ACCESS_TOKEN في أسرار المستودع. لم يُنفَّذ شيء.")
        return 0
    replies = json.loads(CONFIG.read_text(encoding="utf-8"))["replies"]
    active = [r for r in replies if r.get("enabled")]
    print(f"الوضع: {'إرسال فعلي' if LIVE else 'تجربة بلا إرسال'} | ردود مفعّلة: {len(active)}")
    if not active:
        return 0

    me = api("GET", "me", {"fields": "user_id,username"})
    my_id = me.get("user_id") or me.get("id")
    my_username = (me.get("username") or "").lower()
    now = datetime.now(timezone.utc)

    media = api("GET", "me/media", {"fields": "id,timestamp,comments_count", "limit": MEDIA_LIMIT}).get("data", [])
    sent = failed = seen = 0
    for m in media:
        if not m.get("comments_count"):
            continue
        try:
            comments = api("GET", f"{m['id']}/comments", {
                "fields": "id,text,timestamp,username,replies.limit(50){username}",
                "limit": 50,
            }).get("data", [])
        except RuntimeError as e:
            print(f"تعذّرت قراءة تعليقات المنشور {m['id']}: {e}")
            failed += 1
            continue
        for c in comments:
            seen += 1
            if (c.get("username") or "").lower() == my_username:
                continue
            if now - parse_ts(c["timestamp"]) > COMMENT_MAX_AGE:
                continue
            reply = match_reply(c.get("text", ""), replies)
            if not reply or already_handled(c, my_username):
                continue
            if sent >= MAX_SENDS_PER_RUN:
                print("بلغ الحد الأقصى لهذا التشغيل، الباقي في التشغيل القادم.")
                break
            label = f"تعليق {c['id']} → «{reply['name']}»"
            if not LIVE:
                print(f"[تجربة] {label}")
                sent += 1
                continue
            public = reply["public_replies"][int(c["id"][-1:], 36) % len(reply["public_replies"])]
            try:
                api("POST", f"{my_id}/messages", body={
                    "recipient": {"comment_id": c["id"]},
                    "message": {"text": reply["dm"]},
                })
                print(f"أُرسلت الرسالة الخاصة: {label}")
                sent += 1
            except RuntimeError as e:
                # مثلاً: المعلّق لا يستقبل رسائل. نرد علناً حتى لا يبقى بلا جواب ولا نكرر المحاولة.
                print(f"فشلت الرسالة الخاصة: {label}: {e}")
                public = reply.get("fallback_public") or public
                failed += 1
            try:
                api("POST", f"{c['id']}/replies", body={"message": public})
            except RuntimeError as e:
                print(f"فشل الرد العام: {label}: {e}")
                failed += 1
    print(f"الخلاصة: تعليقات مفحوصة {seen} | ردود {sent} | أخطاء {failed}")
    return 1 if failed and not sent else 0


if __name__ == "__main__":
    sys.exit(main())
