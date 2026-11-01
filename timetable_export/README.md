# 課表匯出（.ics 行事曆）

學生／教師可以把自己的課表匯出成 `.ics` 檔，匯入 Google 日曆、Apple 行事曆或 Outlook，
每門課依星期與節次每週自動重複（跨午休的課會自動拆成上午、下午兩段）。

## 這個功能新增的檔案（沒有修改任何既有檔案）

```
timetable_export/            ← 整個資料夾都是新的
    __init__.py
    ics.py                   產生 .ics 內容（純 Python，不依賴 Django）
    views.py                 /export/ 頁面與下載
    urls.py
    dev_settings.py          本機試用用設定（不用改 config/urls.py）
    dev_urls.py              本機試用用路由
    test_ics.py              ics.py 的單元測試
    tests.py                 view / 權限測試
    README.md
templates/timetable_export/
    export.html              頁面模板
```

- 只讀取 `pages.models` 的 `Course`、`Enrollment`，不會寫入資料庫，**不需要 migrate**。
- 不需要加入 `INSTALLED_APPS`。

## 不改任何檔案就能試用

```
python manage.py runserver --settings=timetable_export.dev_settings
```
登入後開啟 http://127.0.0.1:8000/export/

## 執行測試

```
python manage.py test timetable_export
```

## 正式上線（由組長決定要不要做）

在 `config/urls.py` 的 `urlpatterns` 加一行：

```python
path('export/', include('timetable_export.urls')),
```

（選用）在 `templates/base.html` 導覽列「學分進度」按鈕旁加入入口：

```html
{% if request.user.profile.role == 'STUDENT' %}
<a href="{% url 'timetable_export:index' %}" class="btn-settings" title="課表匯出">
    <i class="fa-solid fa-calendar-days"></i> 課表匯出
</a>
{% endif %}
```
