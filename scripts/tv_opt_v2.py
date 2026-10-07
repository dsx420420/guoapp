from pathlib import Path
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()

def read(rel):
    return (root / rel).read_text(encoding="utf-8")

def write(rel, text):
    (root / rel).write_text(text, encoding="utf-8")

def replace_once(text, old, new, label):
    if old not in text:
        raise SystemExit(f"marker not found: {label}")
    return text.replace(old, new, 1)

# Separate package / label for side-by-side testing.
rel = "android/app/build.gradle.kts"
text = read(rel)
text = replace_once(
    text,
    'applicationId = "com.duanju.duanju_app"',
    'applicationId = "com.duanju.duanju_app.tvopt32v2"',
    "applicationId",
)
text = replace_once(
    text,
    'manifestPlaceholders["appLabel"] = if (allSources) "全剧视界" else "短剧视界"',
    'manifestPlaceholders["appLabel"] = if (allSources) "全剧视界TV版V2" else "短剧视界TV版V2"',
    "appLabel",
)
write(rel, text)

# Native Android text dialog, so Xiaomi TV IME gets a real EditText.
rel = "android/app/src/main/kotlin/com/duanju/duanju_app/MainActivity.kt"
text = read(rel)
text = replace_once(
    text,
    "import android.app.UiModeManager\n",
    "import android.app.UiModeManager\nimport android.app.AlertDialog\n",
    "UiModeManager import",
)
text = replace_once(
    text,
    "import android.view.InputDevice\n",
    "import android.view.InputDevice\n"
    "import android.view.WindowManager\n"
    "import android.view.inputmethod.EditorInfo\n"
    "import android.view.inputmethod.InputMethodManager\n"
    "import android.widget.EditText\n"
    "import android.text.InputType\n",
    "InputDevice import",
)

helper_marker = "    override fun onCreate(savedInstanceState: Bundle?) {"
helper = r'''    private fun openTvTextInput(
        initial: String,
        title: String,
        result: MethodChannel.Result
    ) {
        val input = EditText(this).apply {
            setText(initial)
            setSelection(text.length)
            isSingleLine = true
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_CAP_SENTENCES
            imeOptions = EditorInfo.IME_ACTION_SEARCH
            textSize = 20f
            setPadding(32, 20, 32, 20)
        }
        var completed = false
        fun finish(value: String?) {
            if (completed) return
            completed = true
            result.success(value)
        }
        val dialog = AlertDialog.Builder(this)
            .setTitle(title)
            .setView(input)
            .setNegativeButton("取消") { _, _ -> finish(null) }
            .setPositiveButton("确定") { _, _ -> finish(input.text.toString().trim()) }
            .setOnCancelListener { finish(null) }
            .create()
        input.setOnEditorActionListener { _, actionId, _ ->
            if (actionId == EditorInfo.IME_ACTION_SEARCH) {
                finish(input.text.toString().trim())
                dialog.dismiss()
                true
            } else {
                false
            }
        }
        dialog.setOnShowListener {
            input.requestFocus()
            dialog.window?.setSoftInputMode(
                WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_VISIBLE
            )
            input.postDelayed({
                val manager = getSystemService(Context.INPUT_METHOD_SERVICE) as InputMethodManager
                manager.showSoftInput(input, InputMethodManager.SHOW_IMPLICIT)
            }, 180)
        }
        dialog.show()
    }

'''
text = replace_once(text, helper_marker, helper + helper_marker, "onCreate")

method_marker = '                    when (call.method) {\n                        "deviceInfo" -> {'
method_replacement = '''                    when (call.method) {
                        "tvTextInput" -> {
                            openTvTextInput(
                                call.argument<String>("initial").orEmpty(),
                                call.argument<String>("title") ?: "输入剧名",
                                result
                            )
                        }
                        "deviceInfo" -> {'''
text = replace_once(text, method_marker, method_replacement, "MethodChannel")
write(rel, text)

# TV search dialog: D-pad keyboard is primary; native Chinese input is optional.
rel = "lib/remote_widgets.dart"
text = read(rel)
start_marker = "class _TelevisionSearchDialogState extends State<TelevisionSearchDialog> {"
start = text.find(start_marker)
if start < 0:
    raise SystemExit("TV search dialog marker not found")

replacement = r'''class _TelevisionSearchDialogState extends State<TelevisionSearchDialog> {
  late final _controller = TextEditingController(text: widget.initialValue);

  static const _keyboard = <String>[
    'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H',
    'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P',
    'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X',
    'Y', 'Z', '0', '1', '2', '3', '4', '5',
    '6', '7', '8', '9', '空格', '删除', '清空', '中文输入',
    '取消', '搜索',
  ];

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _append(String value) {
    final old = _controller.value;
    final selection = old.selection.isValid
        ? old.selection
        : TextSelection.collapsed(offset: old.text.length);
    final start = selection.start.clamp(0, old.text.length);
    final end = selection.end.clamp(0, old.text.length);
    final next = old.text.replaceRange(start, end, value);
    _controller.value = TextEditingValue(
      text: next,
      selection: TextSelection.collapsed(offset: start + value.length),
    );
    setState(() {});
  }

  void _backspace() {
    final old = _controller.value;
    if (old.text.isEmpty) return;
    final selection = old.selection.isValid
        ? old.selection
        : TextSelection.collapsed(offset: old.text.length);
    var start = selection.start.clamp(0, old.text.length);
    final end = selection.end.clamp(0, old.text.length);
    if (start == end && start > 0) start--;
    _controller.value = TextEditingValue(
      text: old.text.replaceRange(start, end, ''),
      selection: TextSelection.collapsed(offset: start),
    );
    setState(() {});
  }

  Future<void> _nativeChineseInput() async {
    try {
      final value = await const MethodChannel(
        'duanju/device',
      ).invokeMethod<String>(
        'tvTextInput',
        {'initial': _controller.text, 'title': widget.title},
      );
      if (!mounted || value == null) return;
      _controller.value = TextEditingValue(
        text: value,
        selection: TextSelection.collapsed(offset: value.length),
      );
      setState(() {});
    } catch (_) {}
  }

  void _activate(String key) {
    switch (key) {
      case '空格':
        _append(' ');
        break;
      case '删除':
        _backspace();
        break;
      case '清空':
        _controller.clear();
        setState(() {});
        break;
      case '中文输入':
        _nativeChineseInput();
        break;
      case '取消':
        Navigator.pop(context);
        break;
      case '搜索':
        Navigator.pop(context, _controller.text.trim());
        break;
      default:
        _append(key.toLowerCase());
    }
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: Text(widget.title),
    content: SizedBox(
      width: 760,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: double.infinity,
            constraints: const BoxConstraints(minHeight: 60),
            padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.surfaceContainerHighest,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                color: Theme.of(context).colorScheme.outlineVariant,
              ),
            ),
            child: Row(
              children: [
                const Icon(Icons.search_rounded),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    _controller.text.isEmpty ? '请输入剧名' : _controller.text,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontSize: 20,
                      color: _controller.text.isEmpty
                          ? Theme.of(context).colorScheme.onSurfaceVariant
                          : Theme.of(context).colorScheme.onSurface,
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 14),
          Align(
            alignment: Alignment.centerLeft,
            child: Text(
              '遥控器方向键选择；中文请选“中文输入”',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
          ),
          const SizedBox(height: 10),
          SizedBox(
            height: 350,
            child: RemoteGrid(
              itemKeys: _keyboard,
              columns: 8,
              itemExtent: 48,
              spacing: 6,
              padding: EdgeInsets.zero,
              autofocus: true,
              itemBuilder: (_, index, node, onFocus) {
                final key = _keyboard[index];
                return RemoteTarget(
                  focusNode: node,
                  onFocus: onFocus,
                  onPressed: () => _activate(key),
                  radius: 8,
                  borderWidth: 2,
                  outlined: true,
                  padding: EdgeInsets.zero,
                  label: key,
                  child: Center(
                    child: Text(
                      key,
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: key.length > 2 ? 14 : 17,
                        fontWeight: key == '搜索' || key == '中文输入'
                            ? FontWeight.w700
                            : FontWeight.w500,
                      ),
                    ),
                  ),
                );
              },
            ),
          ),
          if (widget.recentSearches.isNotEmpty) ...[
            const SizedBox(height: 8),
            Align(
              alignment: Alignment.centerLeft,
              child: Text(
                '最近搜索：' + widget.recentSearches.take(4).join('  ·  '),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ),
          ],
        ],
      ),
    ),
  );
}
'''
text = text[:start] + replacement
write(rel, text)

# Performance tweaks without reducing the upstream recommendation/card density.
rel = "lib/widgets.dart"
text = read(rel)
text = replace_once(
    text,
    "        cacheWidth: 440,\n",
    "        cacheWidth: AppLayout.isTelevision(context) ? 220 : 440,\n"
    "        filterQuality: AppLayout.isTelevision(context)\n"
    "            ? FilterQuality.low\n"
    "            : FilterQuality.medium,\n",
    "cover cache width",
)
overlay = """        Positioned.fill(
          child: IgnorePointer(
            child: DecoratedBox("""
replacement_overlay = """        if (!AppLayout.isTelevision(context))
          Positioned.fill(
            child: IgnorePointer(
              child: DecoratedBox("""
text = replace_once(text, overlay, replacement_overlay, "cover gradient")
write(rel, text)

# Remove small focus animation on TV only.
rel = "lib/remote_widgets.dart"
text = read(rel)
text = replace_once(
    text,
    "            duration: const Duration(milliseconds: 120),",
    "            duration: AppLayout.isTelevision(context)\n"
    "                ? Duration.zero\n"
    "                : const Duration(milliseconds: 120),",
    "focus animation",
)
write(rel, text)

# Limit decoded image memory in the 32-bit TV process.
rel = "lib/main.dart"
text = read(rel)
if "package:flutter/painting.dart" not in text:
    text = text.replace(
        "import 'package:flutter/material.dart';\n",
        "import 'package:flutter/material.dart';\nimport 'package:flutter/painting.dart';\n",
        1,
    )
marker = "  final device = await AppDevice.detect();\n  runApp(AppBootstrap(device: device));"
replacement_main = """  final device = await AppDevice.detect();
  if (device.television) {
    PaintingBinding.instance.imageCache.maximumSize = 96;
    PaintingBinding.instance.imageCache.maximumSizeBytes = 56 * 1024 * 1024;
  }
  runApp(AppBootstrap(device: device));"""
text = replace_once(text, marker, replacement_main, "main device marker")
write(rel, text)

print("TV V2 patches applied")
