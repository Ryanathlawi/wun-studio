"""
الترجمة: عربي وإنجليزي.

النص العربي نفسه هو المفتاح، فلا حاجة لاختراع مفاتيح ولا لأدوات بناء
إضافية. أي نص بلا ترجمة يظهر بالعربية كما هو بدل أن يختفي.

الوحدة لا تستورد Qt إطلاقًا حتى تبقى core صالحة كمكتبة مستقلة، والاختيار
يُحفظ في ملف JSON بجانب إعدادات المستخدم.
"""

from __future__ import annotations

import json
import os

AR = "ar"
EN = "en"
LANGUAGES = {AR: "العربية", EN: "English"}

_current = AR
_settings_path = None


def settings_file():
    global _settings_path
    if _settings_path is None:
        root = (os.environ.get("APPDATA")
                or os.path.join(os.path.expanduser("~"), ".config"))
        folder = os.path.join(root, "Wun Studio")
        _settings_path = os.path.join(folder, "settings.json")
    return _settings_path


def _read_settings():
    try:
        with open(settings_file(), encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def _write_settings(data):
    path = settings_file()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        return True
    except OSError:
        return False


def load():
    global _current
    stored = _read_settings().get("language")
    if stored in LANGUAGES:
        _current = stored
    return _current


def language():
    return _current


def set_language(code):
    global _current
    if code not in LANGUAGES:
        return False
    _current = code
    data = _read_settings()
    data["language"] = code
    return _write_settings(data)


def other_language():
    return EN if _current == AR else AR


def is_rtl():
    return _current == AR


def t(text):
    if _current == AR:
        return text
    return EN_MAP.get(text, text)


EN_MAP = {
    '\n\nتعذّر حفظ %d ملف.':
        '\n\nCould not save %d file(s).',
    '\n\nتنبيهات:\n':
        '\n\nWarnings:\n',
    '\n\nفشل:\n':
        '\n\nFailed:\n',
    '\n\n⚠ %d من الموارد فيها سكربتات لم تُدمج — راجع fxmanifest يدويًا بعد الدمج.':
        '\n\n⚠ %d of the resources contain scripts that were not merged — review fxmanifest manually afterwards.',
    '\n\n⚠ من بينها %d عملية إعادة ترقيم. لو كانت أرقام القطع مذكورة في ملفات meta أو في سكربتاتك فستحتاج تحديثها يدويًا.':
        '\n\n⚠ %d of them are renumbering operations. If the drawable numbers appear in meta files or in your scripts, you will need to update them by hand.',
    '\n\n⚠ وضع النقل مفعّل: ستُفرَّغ مجلدات stream في الموارد الأصلية ولا يمكن التراجع.':
        '\n\n⚠ Move mode is on: the stream folders in the source resources will be emptied, and this cannot be undone.',
    ' بكسل':
        ' px',
    '%.0f م.ب':
        '%.0f MB',
    '%.1f م.ب':
        '%.1f MB',
    '%.2f جيجا':
        '%.2f GB',
    '%d تكستشر بصيغة غير مدعومة، ستُنسخ كما هي عند الحفظ.':
        '%d textures use an unsupported format and will be copied unchanged on save.',
    '%d ملف · %d قابل للتحسين · %d غير مقروء':
        '%d files · %d optimisable · %d unreadable',
    '%d ملف · %d موديل · %d قطعة · %d تكستشر':
        '%d files · %d models · %d drawables · %d textures',
    '%d ملف خارج نمط التسمية':
        '%d files outside the naming pattern',
    '%d من أصل %d تكستشر في «%s» بصيغة لا يستطيع المحرر فكّها. تظهر باللون البرتقالي وستُنسخ إلى الملف الناتج دون تغيير.':
        '%d of %d textures in “%s” use a format the editor cannot decode. They are shown in orange and will be copied to the output file unchanged.',
    '%d مورد · %d ملف فريد · %s · تصادم %d':
        '%d resources · %d unique files · %s · %d collisions',
    '%d×%d (الأصل %s)':
        '%d×%d (original %s)',
    '%s · %d مستوى':
        '%s · %d levels',
    '%s · الإصدار %s':
        '%s · version %s',
    '%s بلا تكستشر':
        '%s has no texture',
    '%s تكستشر بلا قطعة':
        '%s texture without a drawable',
    '%s ينقصه تنويع %s':
        '%s is missing variant %s',
    '%s — %d (قابل للإصلاح: %d)':
        '%s — %d (fixable: %d)',
    '%s — %d تكستشر':
        '%s — %d textures',
    '%s — اضغط للتفاصيل':
        '%s — click for details',
    '%s — سقف %s':
        '%s — cap %s',
    '%s<br><br>تطوير: <b>%s</b><br>%s':
        '%s<br><br>Built by: <b>%s</b><br>%s',
    '%s^%s ينقصه الرقم %s':
        '%s^%s is missing number %s',
    '<b>%s</b> صار متاحًا.':
        '<b>%s</b> is now available.',
    '<b>%s</b> — الإصدار %s':
        '<b>%s</b> — version %s',
    "description 'دُمج بواسطة Wun Studio من %d مورد: %s'":
        "description 'Merged by Wun Studio from %d resources: %s'",
    'fxmanifest.lua المولّد':
        'Generated fxmanifest.lua',
    'manifest: %s   ·   ملفات جذر: %s':
        'manifest: %s   ·   root files: %s',
    '«%s» فيه تعديلات لم تُحفظ. هل تغلقه وتفقدها؟':
        '“%s” has unsaved edits. Close it and lose them?',
    '، ':
        ', ',
    '، وفشل %d':
        ', %d failed',
    '، وفشلت %d':
        ', %d failed',
    'أخطاء %d · تحذيرات %d · مختار %d مشكلة (%d عملية ملف)':
        '%d errors · %d warnings · %d issues selected (%d file operations)',
    'أسرع ولا يحتاج مساحة إضافية، لكنه يُفرِّغ الموارد الأصلية.':
        'Faster and needs no extra space, but it empties the source resources.',
    'أشكال معبّأة':
        'Filled shapes',
    'أضف مجلدات الموارد التي تريد دمجها. كل مورد يجب أن يحوي مجلد stream بداخله.':
        'Add the resource folders you want to merge. Each resource must contain a stream folder.',
    'أضف موردًا…':
        'Add resource…',
    'أعد التشغيل':
        'Restart',
    'أغلق البرنامج وشغّله يدويًا لتطبيق اللغة الجديدة.':
        'Close the app and start it again yourself to apply the new language.',
    'أغلق دون حفظ':
        'Close without saving',
    'أُصلحت %d عملية':
        '%d operations fixed',
    'أُغلقت كل الملفات':
        'All files closed',
    'أُنشئ المورد في:\n%s\n\nنُقل %d ملف%s.\n\nأضف اسم المورد إلى server.cfg ثم أعد تشغيل السيرفر.':
        'Resource created at:\n%s\n\n%d files transferred%s.\n\nAdd the resource name to server.cfg then restart the server.',
    'إصلاحات':
        'Bug fixes',
    'إظهار شبكة المحاذاة':
        'Show alignment grid',
    'إعادة':
        'Redo',
    'إعادة  (Ctrl+Y)':
        'Redo  (Ctrl+Y)',
    'إعادة الفحص':
        'Rescan',
    'إعادة ترقيم %d ملف':
        'Renumber %d files',
    'إعادة تسمية':
        'Rename',
    'إغلاق':
        'Close',
    'إغلاق ملف معدَّل':
        'Close a modified file',
    'إلغاء':
        'Cancel',
    'إلغاء التحديد':
        'Deselect all',
    'ابحث باسم التكستشر…':
        'Search by texture name…',
    'ابدأ':
        'Start',
    'اجمع عدة موارد ملابس أو سيارات في مورد واحد، مع توليد fxmanifest جاهز وكشف تصادم الأسماء.':
        'Combine several clothing or vehicle resources into one, with a ready fxmanifest and name-collision detection.',
    'احتفظ بأبعاد التكستشر الأصلية':
        'Keep the original texture dimensions',
    'احذف المحدَّد':
        'Remove selected',
    'احفظ نسخة':
        'Save a copy',
    'اختر أداة النص ثم انقر على الكانفس. اسحب النص لتحريكه، وثبّته بـ Ctrl+Enter.':
        'Pick the text tool then click the canvas. Drag the text to move it, and commit it with Ctrl+Enter.',
    'اختر المجلد الذي يُنشأ فيه المورد الناتج':
        'Choose the folder the merged resource will be created in',
    'اختر صورة الختم':
        'Choose the stamp image',
    'اختر مجلد stream داخل مورد الملابس، وسيُفحص كل ما فيه من ملفات ydd و ytd بحثًا عن اليتامى والفجوات.':
        'Choose the stream folder inside the clothing resource; every ydd and ytd in it will be scanned for orphans and gaps.',
    'اختر مجلد الصور المطابقة لأسماء التكستشرات':
        'Choose the folder of images matching the texture names',
    'اختر مجلد الملابس':
        'Choose clothing folder',
    'اختر مجلد الملابس (\u200fstream)':
        'Choose the clothing folder (stream)',
    'اختر مجلد المورد':
        'Choose resource folder',
    'اختر مجلد المورد (الذي يحوي stream)':
        'Choose the resource folder (the one containing stream)',
    'اختر مجلد المورد ثم اضغط «افحص». لن يُكتب شيء — التقرير يوريك كم يمكن توفيره قبل أي قرار.':
        'Choose the resource folder then press “Scan”. Nothing is written — the report shows how much you could save before you decide.',
    'اختر مجلدًا آخر':
        'Choose another folder',
    'اختر مجلدًا لتصدير كل التكستشرات':
        'Choose a folder to export every texture to',
    'اختر مجلدًا لحفظ %d ملف معدَّل':
        'Choose a folder to save %d modified files in',
    'اختر مجلدًا للنسخة المحسّنة':
        'Choose a folder for the optimised copy',
    'اختر مجلدًا يحوي ملفات ytd':
        'Choose a folder containing ytd files',
    'اختم':
        'Stamp',
    'اختيار اللون':
        'Pick colour',
    'اخرج دون حفظ':
        'Quit without saving',
    'ادمج':
        'Merge',
    'ادمج في مورد واحد…':
        'Merge into one resource…',
    'استبدال التكستشر بصورة':
        'Replace texture with an image',
    'استبدال بصورة…':
        'Replace with image…',
    'استرجاع':
        'Revert',
    'استرجاع التكستشر':
        'Revert texture',
    'استرجع':
        'Revert',
    'استعادة':
        'Restore',
    'استورد':
        'Import',
    'استيراد دفعي':
        'Batch import',
    'استيراد مجلد PNG بمطابقة الأسماء…':
        'Import a PNG folder by name matching…',
    'استُبدل %d تكستشر.':
        '%d textures replaced.',
    'استُورد %d تكستشر':
        '%d textures imported',
    'اسحب الصورة لتحريكها، أو اسحب زاوية لتغيير حجمها. ويمكنك ضبط المقاس رقميًا بالأسفل.':
        'Drag the image to move it, or drag a corner to resize it. You can also set the size numerically below.',
    'اسم المورد الناتج':
        'Output resource name',
    'اسم ناقص':
        'Missing name',
    'اسمان يعطيان نفس الـ hash: %s':
        'Two names produce the same hash: %s',
    'افتح صفحة التحديث':
        'Open the update page',
    'افتح على أي حال':
        'Open anyway',
    'افتح ملفات ytd، عدّل تكستشراتها، والصق الصور والنصوص، ثم احفظ ملفًا صالحًا للعبة.':
        'Open ytd files, edit their textures, paste images and text, then save a file the game accepts.',
    'افتح ملفًا أو مجلدًا من الأزرار أعلاه، ثم اختر تكستشرًا من القائمة.':
        'Open a file or a folder from the buttons above, then pick a texture from the list.',
    'افحص':
        'Scan',
    'افحص مورد ملابس كاملًا: قطع بلا تكستشر، فجوات في الترقيم، وملفات يتيمة — مع إصلاح تلقائي.':
        'Scan a whole clothing resource: drawables with no texture, numbering gaps, and orphan files — with automatic fixes.',
    'اكتب اسمًا للمورد الناتج.':
        'Enter a name for the output resource.',
    'اكتب فوقه':
        'Overwrite it',
    'اكتب فوقها':
        'Overwrite them',
    'اكتب نسخة محسّنة…':
        'Write optimised copy…',
    'اكتب نصًا أولًا.':
        'Type some text first.',
    'الأدوات':
        'Tools',
    'الألوان':
        'Colours',
    'الإجراء':
        'Action',
    'الارتفاع':
        'Height',
    'التباين':
        'Contrast',
    'التحديد: %d×%d عند س %d، ص %d':
        'Selection: %d×%d at X %d, Y %d',
    'التدوير والتحجيم والقص تحافظ على أبعاد التكستشر الأصلية، وهو شرط لإعادة كتابته داخل ملف الـ ytd.':
        'Rotate, resize and crop all preserve the original texture dimensions — the condition for writing it back inside the ytd file.',
    'التشبّع':
        'Saturation',
    'التصدير':
        'Export',
    'التكستشر':
        'Texture',
    "التكستشر '%s' يجب أن يكون RGBA بشكل (h, w, 4)":
        "Texture '%s' must be RGBA with shape (h, w, 4)",
    'التكستشرات':
        'Textures',
    'الحجم':
        'Size',
    'الحجم %d أكبر من أن يُمثَّل في أعلام RSC7':
        'Size %d is too large to encode in RSC7 flags',
    'الحجم الأصلي':
        'Actual size',
    'الحجم الأصلي  (Ctrl+1)':
        'Actual size  (Ctrl+1)',
    'الختم يلصق الصورة على كل الملفات المفتوحة بنفس الموضع النسبي، والاستيراد يستبدل كل تكستشر باسمه المطابق.':
        'Stamping pastes the image onto every open file at the same relative position; importing replaces each texture with the image of the same name.',
    'الخصائص':
        'Properties',
    'الخط':
        'Font',
    'الدفعات':
        'Batch',
    'الدلو يملأ المنطقة المتشابهة حول نقطة النقر، والتدرّج يُرسم من اللون الأساسي إلى لون النهاية باتجاه سحبك.':
        'The bucket fills the similar area around the point you click, and the gradient is drawn from the primary colour to the end colour along your drag.',
    'الرجوع إلى الأدوات':
        'Back to tools',
    'السطوع':
        'Brightness',
    'الشفافية':
        'Opacity',
    'الصبغة':
        'Hue',
    'الصور':
        'Images',
    'الصور (*.png *.jpg *.jpeg *.bmp *.tga *.dds *.webp);;كل الملفات (*)':
        'Images (*.png *.jpg *.jpeg *.bmp *.tga *.dds *.webp);;All files (*)',
    'الصورة المختارة':
        'Selected image',
    'الصورة الموضوعة على الكانفس':
        'The image placed on the canvas',
    'الصيغ فقط':
        'Formats only',
    'الصيغة %s غير مدعومة للكتابة':
        'Format %s is not supported for writing',
    'العرض':
        'Width',
    'القطعة موجودة بلا أي ملف تكستشر، فتظهر في اللعبة بلا خامة.':
        'The drawable exists with no texture file at all, so it appears untextured in game.',
    'الكتابة فوق الملف الأصلي':
        'Overwrite the original file',
    'الكتابة فوق الملفات الأصلية':
        'Overwrite the original files',
    'اللون':
        'Colour',
    'المجلد «%s» موجود وغير فارغ. المتابعة قد تخلط الملفات.\n\nهل تتابع؟':
        'Folder “%s” exists and is not empty. Continuing may mix the files together.\n\nContinue?',
    'المجلد المختار هو نفسه مجلد %d من الملفات المفتوحة، وستُكتب نسخها الأصلية فوقها:\n\n%s\n\nلا يمكن التراجع. هل تتابع؟':
        'The chosen folder is the same folder as %d of the open files, and their originals will be overwritten:\n\n%s\n\nThis cannot be undone. Continue?',
    'المجلد غير موجود':
        'Folder not found',
    'المجلد كبير':
        'Large folder',
    'المجلد موجود':
        'Folder exists',
    'المجلد يحوي أكثر من %d ملف؛ فُتحت أول %d فقط.':
        'The folder holds more than %d files; only the first %d were opened.',
    'المسار الناتج يطابق أحد الموارد المصدر.':
        'The output path matches one of the source resources.',
    'المعاينة فورية على نسخة مصغّرة، و«تطبيق» يعيد الحساب على الدقة الكاملة.':
        'The preview is instant on a downscaled copy, and “Apply” recomputes at full resolution.',
    'المقاس':
        'Size',
    'الملاحة':
        'Navigator',
    'الملف / التكستشر':
        'File / texture',
    'الموارد المضافة':
        'Added resources',
    'المورد':
        'Resource',
    'المورد سليم':
        'Resource is clean',
    'النص':
        'Text',
    'امسح':
        'Clear',
    'انقل بدل النسخ':
        'Move instead of copy',
    'بعد':
        'After',
    'بعض التكستشرات غير مقروءة':
        'Some textures are unreadable',
    'بلا تصغير':
        'no downscale',
    'بيانات البكسل %s ← %s   ·   التوفير %s (%.0f%%)   ·   %d تكستشر صُغّر، %d غيّر صيغته':
        'Pixel data %s → %s   ·   saving %s (%.0f%%)   ·   %d textures downscaled, %d reformatted',
    'بيضاوي':
        'Ellipse',
    'تابع':
        'Continue',
    'تثبيت الصورة':
        'Commit image',
    'تثبيت النص':
        'Commit text',
    'تحجيم المحتوى':
        'Scale content',
    'تحجيم…':
        'Resize…',
    'تحديث':
        'Update',
    'تحديث %s':
        'Update %s',
    'تحديث كبير':
        'Major update',
    'تحديد %d×%d':
        'Selection %d×%d',
    'تحديد الكل':
        'Select all',
    'تحديد كل القابل للإصلاح':
        'Select everything fixable',
    'تحديد مستطيل':
        'Rectangular select',
    'تحريك اللوحة':
        'Pan',
    'تدرّج رمادي':
        'Grayscale',
    'تدرّج لوني':
        'Gradient',
    'تدوير':
        'Rotate',
    'تدوير تكستشر غير مربّع يبدّل عرضه بارتفاعه (%d×%d يصير %d×%d)، فلا يعود قابلًا للكتابة داخل هذا الملف.\n\nهل تريد التدوير على أي حال؟':
        'Rotating a non-square texture swaps its width and height (%d×%d becomes %d×%d), so it can no longer be written back into this file.\n\nRotate anyway?',
    'تدوير يسارًا':
        'Rotate left',
    'تدوير يمينًا':
        'Rotate right',
    'تراجع':
        'Undo',
    'تراجع  (Ctrl+Z)':
        'Undo  (Ctrl+Z)',
    'ترقيم القطع يجب أن يكون متصلًا من صفر، وإلا انزاحت الفهارس في اللعبة فتختار قطعة وتظهر غيرها.':
        'Drawable numbering must run continuously from zero, otherwise the in-game indices shift and picking one drawable shows another.',
    'تسامح الدلو':
        'Bucket tolerance',
    'تصادم أسماء — %d ملف':
        'Name collisions — %d files',
    'تصدير DDS':
        'Export DDS',
    'تصدير DDS يكتب بيانات السطح كما هي داخل الملف، لا تعديلاتك غير المحفوظة.':
        'Exporting DDS writes the surface data as it is inside the file, not your unsaved edits.',
    'تصدير PNG':
        'Export PNG',
    'تصدير دفعي':
        'Batch export',
    'تصدير كل التكستشرات PNG…':
        'Export every texture as PNG…',
    'تصغير':
        'Minimize',
    'تصغير  (Ctrl -)':
        'Zoom out  (Ctrl -)',
    'تصغير %d→%d':
        'downscale %d→%d',
    'تصفير':
        'Reset',
    'تطبيق':
        'Apply',
    'تطبيق الإصلاحات':
        'Apply fixes',
    'تعديلات غير محفوظة':
        'Unsaved changes',
    'تعذّر تحميل الصورة':
        'Could not load the image',
    'تعذّر حفظ اللغة':
        'Could not save the language',
    'تعذّر فتح «%s»':
        'Could not open “%s”',
    'تعذّر فكّ التكستشر':
        'Could not decode the texture',
    'تعذّر لصق الصورة':
        'Could not paste the image',
    'تعذّرت إعادة التشغيل':
        'Could not restart',
    "تعذّرت كتابة '%s':\n%s":
        "Could not write '%s':\n%s",
    'تغيير اللغة':
        'Change language',
    'تغيير اللغة يعيد تشغيل البرنامج، وعندك تعديلات لم تُحفظ في %d ملف:\n\n%s\n\nهل تتابع دون حفظها؟':
        'Changing the language restarts the app, and you have unsaved edits in %d files:\n\n%s\n\nContinue without saving them?',
    'تغيير لغة الواجهة  (يعيد تشغيل البرنامج)':
        'Change the interface language  (restarts the app)',
    'تفريغ':
        'Clear all',
    'تقرير الضغط':
        'Optimisation report',
    'تكبير':
        'Zoom in',
    'تكبير  (Ctrl +)':
        'Zoom in  (Ctrl +)',
    'تكستشر DDS (*.dds)':
        'DDS texture (*.dds)',
    'تكستشر غير قابل للتحرير':
        'Texture is not editable',
    'تكستشرات بلا قطعة':
        'Textures without a drawable',
    'تم الحفظ':
        'Saved',
    'تمّ الإصلاح':
        'Fixed',
    'تمّ الاستيراد':
        'Imported',
    'تمّ التصدير':
        'Exported',
    'تمّ الختم':
        'Stamped',
    'تمّ الدمج':
        'Merged',
    'تمّت الكتابة':
        'Written',
    'توجد %d تكستشرات بلا ملف ydd يقابلها، وهي وزن ميت في المورد.':
        'There are %d textures with no matching ydd file — dead weight in the resource.',
    'توجد تعديلات غير محفوظة':
        'There are unsaved changes',
    'توفير %d%%':
        'saves %d%%',
    'جاري إعادة الترميز…':
        'Re-encoding…',
    'جاري الاستيراد…':
        'Importing…',
    'جاري التصدير…':
        'Exporting…',
    'جاري الختم…':
        'Stamping…',
    'جاري الدمج…':
        'Merging…',
    'جاري بناء معاينات التكستشرات…':
        'Building texture previews…',
    'جاري حفظ %s…':
        'Saving %s…',
    'جاري حفظ الملفات…':
        'Saving files…',
    'جاري فحص الملفات…':
        'Scanning files…',
    'جاهز':
        'Ready',
    'حافظ على النسبة':
        'Keep aspect ratio',
    "حجم البيانات الخام لـ '%s' لا يطابق المتوقع (%d مقابل %d)":
        "Raw data size for '%s' does not match the expected size (%d vs %d)",
    'حدّد منطقة بأداة التحديد أولًا، ثم أعد المحاولة.':
        'Select an area with the selection tool first, then try again.',
    'حرّك أحد المنزلقات أولًا.':
        'Move one of the sliders first.',
    'حسنًا':
        'OK',
    'حفظ الكل':
        'Save all',
    'حفظ باسم':
        'Save as',
    'حواف ناعمة':
        'Antialiasing',
    'حُفظ %d ملف في %s':
        '%d files saved to %s',
    'حُفظ %s':
        '%s saved',
    'حُفظ مع تنبيهات':
        'Saved with warnings',
    'ختم دفعي':
        'Batch stamp',
    'ختم صورة على كل الملفات…':
        'Stamp an image onto every file…',
    'خرائط':
        'Maps',
    'خط':
        'Line',
    'خطأ غير متوقع أثناء قراءة الملف:\n\n%s\n\n%s':
        'Unexpected error while reading the file:\n\n%s\n\n%s',
    'خطأ غير متوقع أثناء كتابة الملف:\n\n%s\n\n%s':
        'Unexpected error while writing the file:\n\n%s\n\n%s',
    'خُتم %d تكستشر':
        '%d textures stamped',
    'خُتم %d تكستشر في %d ملف.':
        '%d textures stamped across %d files.',
    'دلو تعبئة':
        'Paint bucket',
    'دمج الموارد':
        'Merge resources',
    'دوّر':
        'Rotate',
    'دُمج %d ملف في %s':
        '%d files merged into %s',
    'رفع صورة':
        'Place image',
    'رفع صورة…':
        'Place image…',
    'س':
        'X',
    'س %d، ص %d':
        'X %d, Y %d',
    'ستُكتب %d ملف في:\n%s\n\nالتوفير المتوقع %s. الملفات غير المتغيّرة تُنسخ كما هي، والمورد الأصلي لا يُلمس.\n\nإعادة الترميز تستغرق وقتًا على الموارد الكبيرة. هل تتابع؟':
        '%d files will be written to:\n%s\n\nExpected saving %s. Unchanged files are copied as they are, and the source resource is never touched.\n\nRe-encoding takes a while on large resources. Continue?',
    'ستُنفَّذ %d عملية على الملفات: %s.\n\nلم يُكتب أي شيء بعد.':
        '%d operations will run on the files: %s.\n\nNothing has been written yet.',
    'ستُنفَّذ %d عملية على ملفات المورد، ولا يمكن التراجع تلقائيًا.%s\n\nهل أخذت نسخة احتياطية؟':
        '%d operations will run on the resource files, and they cannot be undone automatically.%s\n\nDo you have a backup?',
    'سقف الأبعاد':
        'Dimension cap',
    'سيارات':
        'Vehicles',
    'سيُستبدل %d تكستشر بصور مطابقة الاسم، وكل صورة ستُمدّد إلى أبعاد التكستشر الأصلية.\n\nلن يُكتب أي ملف قبل «حفظ الكل». هل تتابع؟':
        '%d textures will be replaced with name-matched images, and every image will be stretched to the original texture dimensions.\n\nNo file is written before “Save all”. Continue?',
    'سيُعاد تشغيل البرنامج لتطبيق اللغة الجديدة.\n\nهل تتابع؟':
        'The app will restart to apply the new language.\n\nContinue?',
    'سيُكتب فوق الملف الذي فتحته:\n\n%s\n\nلا يمكن التراجع بعد الكتابة. هل تتابع؟':
        'The file you opened will be overwritten:\n\n%s\n\nThis cannot be undone once written. Continue?',
    'سيُلصق %s على %d تكستشر داخل %d ملف، بنفس الموضع النسبي.\n\nلن يُكتب أي ملف على القرص قبل أن تضغط «حفظ الكل»، فتقدر تراجع النتيجة أولًا.\n\nهل تتابع؟':
        '%s will be pasted onto %d textures across %d files, at the same relative position.\n\nNothing is written to disk until you press “Save all”, so you can review the result first.\n\nContinue?',
    'سيُنشأ مورد باسم «%s» فيه %d ملف بحجم %s.%s\n\nهل تتابع؟':
        'A resource named “%s” will be created with %d files totalling %s.%s\n\nContinue?',
    'ص':
        'Y',
    'صدر في %s':
        'Released %s',
    'صغّر حجم مورد كامل — ملابس أو سيارات أو خرائط — بتصغير التكستشرات المبالغ فيها وتحويل الصيغ الزائدة.':
        'Shrink a whole resource — clothing, vehicles or maps — by downscaling oversized textures and converting wasteful formats.',
    'صورة PNG (*.png)':
        'PNG image (*.png)',
    'صُدِّر %d تكستشر':
        '%d textures exported',
    'صُدِّر %d تكستشر إلى:\n%s':
        '%d textures exported to:\n%s',
    'صُدِّر %s':
        '%s exported',
    'صُدِّر DDS':
        'DDS exported',
    'صُدِّرت بيانات السطح كما هي مخزّنة داخل ملف الـ ytd.\n\nملاحظة: هذه ليست تعديلاتك غير المحفوظة على الكانفس.':
        'The surface data was exported exactly as it is stored inside the ytd file.\n\nNote: this is not your unsaved work on the canvas.',
    'ضغط أقصى':
        'Maximum compression',
    'ضغط الموارد':
        'Resource optimiser',
    'ضغط المورد':
        'Optimise resource',
    'طبّق الآن':
        'Apply now',
    'طُبّقت التعديلات اللونية':
        'Colour adjustments applied',
    'عدد التكستشرات يتجاوز الحد':
        'Texture count exceeds the limit',
    'عرض التفاصيل':
        'Show details',
    'عريض':
        'Bold',
    'عكس الألوان':
        'Invert',
    'عن البرنامج':
        'About',
    'غير مقروء':
        'unreadable',
    'فتح كل ملفات ytd داخل مجلد  (Ctrl+Shift+O)':
        'Open every ytd file inside a folder  (Ctrl+Shift+O)',
    'فتح مجلد':
        'Open folder',
    'فتح ملف ytd أو عدة ملفات معًا  (Ctrl+O)':
        'Open one ytd file or several at once  (Ctrl+O)',
    'فتح ملفات':
        'Open files',
    'فتح ملفات تكستشرات':
        'Open texture files',
    'فجوات في ترقيم القطع':
        'Gaps in drawable numbering',
    'فجوات في حروف التنويعات':
        'Gaps in variant letters',
    'فجوة في حروف التنويعات تجعل اللعبة تقرأ تنويعًا غير موجود.':
        'A gap in the variant letters makes the game read a variant that does not exist.',
    'فحص المورد':
        'Scanning resource',
    'فرشاة':
        'Brush',
    'فشل التصدير':
        'Export failed',
    'فشل الحفظ':
        'Save failed',
    'فُتح %d ملف — اختر ملفًا من القائمة':
        '%d files open — pick one from the list',
    'فُحص %s — %d مشكلة':
        'Scanned %s — %d issues',
    'فُحص %s — توفير %s':
        'Scanned %s — saves %s',
    'قاموس تكستشرات GTA V (*.ytd);;كل الملفات (*)':
        'GTA V texture dictionary (*.ytd);;All files (*)',
    'قبل':
        'Before',
    'قريبًا':
        'Coming soon',
    'قص':
        'Crop',
    'قصّ على التحديد':
        'Crop to selection',
    'قص…':
        'Crop…',
    'قطع بلا تكستشر':
        'Drawables with no texture',
    'قلب أفقي':
        'Flip horizontally',
    'قلب رأسي':
        'Flip vertically',
    'قُرئ الملف لكنه لا يحتوي على بكسلات صالحة.':
        'The file was read but holds no valid pixels.',
    'كتابة النسخة المحسّنة':
        'Write the optimised copy',
    'كتابة كل الملفات المعدَّلة إلى مجلد  (Ctrl+Alt+S)':
        'Write every modified file to a folder  (Ctrl+Alt+S)',
    'كتابة ملف ytd جديد بتعديلاتك  (Ctrl+Shift+S)':
        'Write a new ytd file with your edits  (Ctrl+Shift+S)',
    'كل التكستشرات ضمن السقف المختار ولا توجد صيغ زائدة. جرّب سقفًا أصغر أو نمطًا أقوى.':
        'Every texture is within the chosen cap and there are no wasteful formats. Try a smaller cap or a stronger preset.',
    'كل التكستشرات قابلة للتحرير.':
        'All textures are editable.',
    'كُتب %d ملف في:\n%s':
        '%d files written to:\n%s',
    'كُتب %d ملف محسّن، ونُسخ %d كما هو%s.\n\nالحجم على القرص: %s ← %s (توفير %.0f%%)':
        '%d optimised files written, %d copied unchanged%s.\n\nSize on disk: %s → %s (saves %.0f%%)',
    'كُتب %s\n\nحُدِّث %d تكستشر.':
        '%s written\n\n%d textures updated.',
    'كُتبت نسخة محسّنة في %s':
        'Optimised copy written to %s',
    'لا توجد تعديلات':
        'No changes',
    'لا توجد تكستشرات قابلة للتحرير.':
        'No editable textures.',
    'لا توجد تكستشرات قابلة للكتابة في %s':
        'No writable textures in %s',
    'لا توجد صور':
        'No images',
    'لا توجد ملفات':
        'No files',
    'لا شيء':
        'None',
    'لا يمكن الكتابة داخل المورد الأصلي. اختر مجلدًا فارغًا حتى يبقى الأصل سليمًا.':
        'Cannot write inside the source resource. Choose an empty folder so the original stays intact.',
    'لا يمكن بناء قاموس بلا تكستشرات':
        'Cannot build a dictionary with no textures',
    'لا يوجد':
        'none',
    'لا يوجد تحديد':
        'No selection',
    'لا يوجد تطابق':
        'No matches',
    'لا يوجد تعديل':
        'No edits',
    'لا يوجد تكستشر':
        'No texture',
    'لا يوجد ما يُثبَّت':
        'Nothing to commit',
    'لا يوجد ما يُضغط':
        'Nothing to optimise',
    'لا يوجد مجلد stream داخل المورد':
        'No stream folder inside the resource',
    'لا يوجد ملف مفتوح':
        'No file open',
    'لا يوجد هدف':
        'No target',
    'لاحقًا':
        'Later',
    'لديك تعديلات لم تُحفظ في %d ملف:\n\n%s\n\nهل تخرج دون حفظها؟':
        'You have unsaved edits in %d files:\n\n%s\n\nQuit without saving them?',
    'لديك تعديلات لم تُحفظ. هل تفتح ملفات أخرى رغم ذلك؟':
        'You have unsaved edits. Open other files anyway?',
    'لم يُختر تكستشر':
        'No texture selected',
    'لم يُختر مجلد بعد':
        'No folder chosen yet',
    'لم يُضَف أي مورد':
        'No resource added',
    'لم يُعثر على أي صورة داخل:\n\n%s':
        'No image was found in:\n\n%s',
    'لم يُعثر على أي ملف ytd داخل:\n\n%s':
        'No ytd file was found in:\n\n%s',
    'لم يُعثر على يتامى ولا فجوات في التسمية أو الترقيم.':
        'No orphans and no gaps in naming or numbering were found.',
    'لم يُعدَّل أي تكستشر في «%s». هل تحفظ نسخة منه رغم ذلك؟':
        'No texture in “%s” was modified. Save a copy of it anyway?',
    'لم يُعدَّل أي ملف من الملفات المفتوحة.':
        'None of the open files were modified.',
    'لم يُفتح أي ملف بعد':
        'No file opened yet',
    'لم يُفحص أي مورد بعد':
        'No resource scanned yet',
    'لم يُكتب ملف الإعدادات، فستعود اللغة كما كانت عند إعادة التشغيل.':
        'The settings file could not be written, so the language would revert on restart.',
    'لُصقت %s بمقاس %d×%d — اسحبها لتحريكها ثم اضغط «تثبيت الصورة»':
        '%s pasted at %d×%d — drag it to move it, then press “Commit image”',
    'مائل':
        'Italic',
    'مجلد stream داخل المورد':
        'The stream folder inside the resource',
    'مجلد stream داخل مورد الملابس':
        'The stream folder inside the clothing resource',
    'محتوى النص':
        'Text content',
    'محرّر التكستشرات':
        'Texture editor',
    'محرّر تكستشرات GTA V و FiveM':
        'GTA V & FiveM texture editor',
    'مدقّق الملابس':
        'Clothing doctor',
    'مزايا جديدة':
        'New features',
    'مستطيل':
        'Rectangle',
    'مسح':
        'Erase',
    'مسح الكانفس':
        'Clear canvas',
    'مطلوب لإعادة الحفظ داخل ملف الـ ytd. إلغاء هذا الخيار يغيّر أبعاد الكانفس فلا يعود التكستشر قابلًا للكتابة في مكانه.':
        'Required in order to save back inside the ytd file. Turning this off changes the canvas dimensions, so the texture can no longer be written in place.',
    'معاينة جافة':
        'Dry run',
    'مقارنة قبل / بعد':
        'Before / after',
    'مقاس الشبكة':
        'Grid size',
    'ملء التكستشر':
        'Fill texture',
    'ملء الشاشة  (Ctrl+0)':
        'Fit to window  (Ctrl+0)',
    'ملابس':
        'Clothing',
    'ملفات':
        'Files',
    'ملفات خارج نمط التسمية':
        'Files outside the naming pattern',
    'ملفات لا تطابق نمط model^component_NNN. قد تكون ملفات أساس للموديل نفسه وليست ملابس.':
        'Files that do not match the model^component_NNN pattern. They may be base files for the model itself rather than clothing.',
    'ملقاط ألوان':
        'Colour picker',
    'ممحاة':
        'Eraser',
    'موضع المقسّم':
        'Splitter position',
    'نتيجة الفحص':
        'Scan result',
    'نسخ':
        'Copy',
    'نسخ %s':
        'Copy %s',
    'نسخ أقرب تنويع سابق':
        'Copy the nearest earlier variant',
    'نسختك الحالية: %s':
        'You have: %s',
    'نص':
        'Text',
    'نص جديد':
        'New text',
    'نعم':
        'Yes',
    'نقل':
        'Move',
    'نقل %d ملف إلى مجلد _unused':
        'Move %d files to the _unused folder',
    'نهاية التدرّج':
        'Gradient end',
    'نوع التحديث: %s':
        'Update type: %s',
    'نُفِّذت %d عملية بنجاح%s.':
        '%d operations completed successfully%s.',
    'هل تتجاهل كل تعديلاتك على «%s» وتعيد تحميله من الملف؟':
        'Discard all your edits to “%s” and reload it from disk?',
    'هل تمسح التكستشر بالكامل ليصير شفافًا؟':
        'Clear the whole texture so it becomes transparent?',
    'وُجدت %d صورة لكن لا يطابق اسمها أي تكستشر مفتوح.\n\nاسم الملف يجب أن يطابق اسم التكستشر تمامًا بلا امتداد.':
        '%d images were found, but none of their names match an open texture.\n\nThe file name must match the texture name exactly, without the extension.',
    'يتوفّر إصدار أحدث: %s':
        'A newer version is available: %s',
    'يتوفّر تحديث':
        'Update available',
    'يُؤخذ من %s ويُتجاهل من %s':
        'taken from %s, ignored from %s',
    '٪':
        '%',
    '⚠ هذا المورد فيه سكربتات — راجعها يدويًا بعد الدمج':
        '⚠ This resource contains scripts — review them manually after merging',
}
