# 🏡 FurnitureAI — Blueprint to Design

> نظام ذكاء اصطناعي متكامل لتصميم الأثاث من مخططات المعمارية — مع تكامل IKEA و Alibaba.

---

## 🗂️ هيكل المشروع

```
furniture-ai/
│
├── main.py                        # ← نقطة الدخول الموحدة (يشغّل الـ backend)
├── requirements.txt               # ← كل تبعيات Python
├── package.json                   # ← تبعيات Node.js (frontend)
├── vite.config.js                 # ← إعداد Vite
├── tailwind.config.js             # ← إعداد Tailwind CSS
├── postcss.config.js
│
├── backend/                       # ← الـ Backend (FastAPI)
│   ├── main.py                    #   تعريف تطبيق FastAPI + middleware
│   ├── api/                       #   نقاط النهاية (Endpoints)
│   │   ├── analyze.py             #     تحليل المخططات (YOLO)
│   │   ├── recommend.py           #     توصيات الأثاث
│   │   ├── layout3d.py            #     توليد التخطيط ثلاثي الأبعاد
│   │   ├── catalog.py             #     كتالوج IKEA + Alibaba
│   │   └── ai_assist.py           #     مساعد AI (Qwen/DashScope)
│   ├── services/                  #   طبقة الخدمات
│   │   ├── yolo_service.py        #     كشف الغرف من الصور
│   │   ├── rec_service.py         #     محرك التوصيات
│   │   ├── layout_service.py      #     توليد المشاهد ثلاثية الأبعاد
│   │   ├── ikea_service.py        #     كتالوج IKEA
│   │   ├── alibaba_service.py     #     كتالوج Alibaba
│   │   └── dashscope_service.py   #     Qwen LLM (Alibaba Cloud)
│   ├── models/
│   │   └── pydantic_schemas.py    #   نماذج البيانات (Pydantic)
│   ├── core/
│   │   └── config.py              #   الإعدادات (env vars)
│   └── logging/
│       └── logger.py              #   نظام السجلات (JSON)
│
├── frontend/                      # ← الـ Frontend (React + Vite)
│   ├── index.html
│   └── src/
│       ├── main.jsx               #   نقطة دخول React
│       ├── App.jsx                #   التطبيق الرئيسي + التنقل
│       ├── styles.css             #   Tailwind + أنماط مخصصة
│       ├── api/
│       │   └── api.js             #   طبقة HTTP (axios)
│       ├── pages/
│       │   ├── BlueprintStudio.jsx  # صفحة رفع وتحليل المخططات
│       │   ├── FurnitureCatalog.jsx # كتالوج الأثاث مع فلاتر
│       │   └── DesignStudio.jsx     # استوديو التصميم ثلاثي الأبعاد
│       └── components/
│           ├── FurnitureCard.jsx  #   بطاقة منتج الأثاث
│           ├── RoomCard.jsx       #   بطاقة الغرفة المكتشفة
│           ├── Viewer3D.jsx       #   عارض Three.js ثلاثي الأبعاد
│           └── FileUploader.jsx   #   مكوّن رفع الملفات
│
└── scripts/                       # ← سكريبتات مساعدة
    ├── datasets/                  #   بناء وجلب مجموعات البيانات
    │   ├── fetch.py               #     جلب مستودعات المخططات
    │   ├── preprocess.py          #     معالجة الصور + تسميات YOLO
    │   ├── build_furniture.py     #     بناء كتالوج CSV
    │   └── build_3d.py            #     بناء بيانات المشاهد ثلاثية الأبعاد
    ├── train/                     #   تدريب النماذج
    │   ├── train_yolo.py          #     تدريب نموذج YOLO
    │   ├── train_recommender.py   #     تدريب نموذج التوصيات
    │   └── train_3d.py            #     تدريب نموذج التخطيط ثلاثي الأبعاد
    └── auto/                      #   أتمتة + cron
        ├── sync.py                #     مزامنة git تلقائية
        ├── train.py               #     تشغيل التدريب الدوري
        ├── update.py              #     تحديث البيانات
        └── cron/
            └── cron.py            #     جدولة المهام
```

---

## 🚀 التشغيل السريع

### Backend (Python)

```bash
# تثبيت التبعيات
pip install -r requirements.txt

# تشغيل الخادم
python main.py
# أو مباشرةً:
uvicorn backend.main:app --reload --port 8000
```

الـ API يعمل على: `http://localhost:8000`  
التوثيق التفاعلي: `http://localhost:8000/docs`

### Frontend (React)

```bash
# تثبيت التبعيات
npm install

# تشغيل بيئة التطوير
npm run dev
# يعمل على: http://localhost:5173

# بناء للإنتاج
npm run build
```

---

## 🔌 نقاط النهاية (API Endpoints)

| الطريقة | المسار | الوصف |
|---------|--------|-------|
| `POST` | `/analyze/blueprint` | تحليل مخطط معماري واكتشاف الغرف |
| `POST` | `/recommend/furniture` | توصيات أثاث مخصصة |
| `POST` | `/layout3d/generate` | توليد تخطيط ثلاثي الأبعاد |
| `GET`  | `/catalog/products` | تصفح كتالوج IKEA + Alibaba |
| `GET`  | `/catalog/categories` | قائمة الفئات المتاحة |
| `POST` | `/ai/room-plan` | خطة أثاث بالذكاء الاصطناعي |
| `POST` | `/ai/color-palette` | اقتراح لوحة ألوان |
| `POST` | `/ai/enrich-description` | تحسين وصف المنتج بـ Qwen AI |
| `GET`  | `/health` | فحص حالة الخادم |

---

## ⚙️ متغيرات البيئة

```env
FURNITURE_DASHSCOPE_API_KEY=sk-...   # مفتاح Alibaba Cloud DashScope
FURNITURE_DASHSCOPE_MODEL=qwen-turbo
FURNITURE_YOLO_MODEL_PATH=models/yolo/best.pt
FURNITURE_RECOMMENDER_MODEL_PATH=models/recommender/model.pt
FURNITURE_LAYOUT_MODEL_PATH=models/layout3d/model.pt
```

---

## 🛠️ سكريبتات البيانات والتدريب

```bash
# جلب مجموعات بيانات المخططات
python scripts/datasets/fetch.py

# معالجة الصور وتوليد تسميات YOLO
python scripts/datasets/preprocess.py

# بناء كتالوج الأثاث
python scripts/datasets/build_furniture.py

# تدريب النماذج
python scripts/train/train_yolo.py
python scripts/train/train_recommender.py
python scripts/train/train_3d.py

# تشغيل جدولة المهام التلقائية
python scripts/cron/cron.py
```

---

## 🏗️ التقنيات المستخدمة

| الطبقة | التقنية |
|--------|---------|
| Backend | FastAPI, Pydantic, Uvicorn |
| AI/ML | YOLO (Ultralytics), Qwen LLM (DashScope) |
| Frontend | React 18, Vite, Tailwind CSS, Three.js |
| كتالوج | IKEA API, Alibaba Catalog |
| صور | Pillow, CairoSVG |
