import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

interface ImageEditorProps {
  imageId: string;
  onAnalysisComplete: (analysis: any) => void;
}

interface EditParams {
  brightness: number; contrast: number; saturation: number; temperature: number;
  sharpness: number; highlights: number; shadows: number;
  vignette: number; grain: number; tint: number; fade: number; hue_shift: number;
}

interface StyleInfo {
  id: string; label_zh: string; description: string; category: string;
  params: EditParams;
}

interface CustomPreset {
  id: string; name: string; created_at: string;
  brightness: number; contrast: number; saturation: number; temperature: number;
  sharpness: number; highlights: number; shadows: number;
  vignette: number; grain: number; tint: number; fade: number; hue_shift: number;
}

const CATEGORY_ORDER = ['基础', '氛围', '胶片', '地域', '社交', '艺术', '自定义'];

const DEFAULT_PARAMS: EditParams = {
  brightness: 0, contrast: 0, saturation: 0, temperature: 0,
  sharpness: 0, highlights: 0, shadows: 0,
  vignette: 0, grain: 0, tint: 0, fade: 0, hue_shift: 0,
};

type ParamKey = keyof EditParams;

// ── Slider definitions ────────────────────────────────────
interface SliderDef {
  key: ParamKey; label: string; min: number; max: number; step: number;
  section: string;
}

const SLIDERS: SliderDef[] = [
  { key: 'brightness',  label: '亮度',   min: -1,  max: 1,   step: 0.1, section: '基本' },
  { key: 'contrast',    label: '对比度', min: -50, max: 50,  step: 5,   section: '基本' },
  { key: 'saturation',  label: '饱和度', min: -50, max: 50,  step: 5,   section: '基本' },
  { key: 'temperature', label: '色温',   min: -50, max: 50,  step: 5,   section: '基本' },
  { key: 'tint',        label: '色调',   min: -50, max: 50,  step: 5,   section: '基本' },
  { key: 'highlights',  label: '高光',   min: -50, max: 50,  step: 5,   section: '光影' },
  { key: 'shadows',     label: '阴影',   min: -50, max: 50,  step: 5,   section: '光影' },
  { key: 'fade',        label: '褪色',   min: 0,   max: 100, step: 5,   section: '光影' },
  { key: 'sharpness',   label: '锐度',   min: -50, max: 50,  step: 5,   section: '质感' },
  { key: 'vignette',    label: '暗角',   min: 0,   max: 100, step: 5,   section: '质感' },
  { key: 'grain',       label: '颗粒',   min: 0,   max: 100, step: 5,   section: '质感' },
  { key: 'hue_shift',   label: '色相偏移', min: -30, max: 30, step: 5,  section: '色彩' },
];

const SECTIONS = ['基本', '光影', '质感', '色彩'];

const ImageEditor: React.FC<ImageEditorProps> = ({ imageId, onAnalysisComplete }) => {
  const [loading, setLoading] = useState(false);
  const [analysis, setAnalysis] = useState<any>(null);
  const [editedImageId, setEditedImageId] = useState<string | null>(null);
  const [editParams, setEditParams] = useState<EditParams>({...DEFAULT_PARAMS});
  const [error, setError] = useState<string | null>(null);

  // Style system
  const [builtinStyles, setBuiltinStyles] = useState<StyleInfo[]>([]);
  const [customPresets, setCustomPresets] = useState<CustomPreset[]>([]);
  const [selectedStyleId, setSelectedStyleId] = useState<string | null>(null);
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [presetName, setPresetName] = useState('');
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['基本']));

  // ── Fetch styles ─────────────────────────────────────────
  const fetchStyles = useCallback(async () => {
    try {
      const { data } = await axios.get('/api/v1/presets/styles');
      setBuiltinStyles(data.builtin || []);
      setCustomPresets(data.custom || []);
    } catch { /* silent */ }
  }, []);

  useEffect(() => { fetchStyles(); }, [fetchStyles]);

  // ── Analyze image ───────────────────────────────────────
  useEffect(() => {
    const analyze = async () => {
      setLoading(true);
      try {
        const { data } = await axios.post('/api/v1/analysis/analyze', { image_id: imageId });
        setAnalysis(data);
        onAnalysisComplete(data);
      } catch { setError('分析失败'); }
      finally { setLoading(false); }
    };
    analyze();
  }, [imageId, onAnalysisComplete]);

  // ── Select style → load params ──────────────────────────
  const handleSelectStyle = (style: StyleInfo | CustomPreset) => {
    const isCustom = 'name' in style && !('label_zh' in style);
    const src = isCustom ? style : (style as StyleInfo).params;
    setEditParams({
      brightness: src.brightness ?? 0,
      contrast: src.contrast ?? 0,
      saturation: src.saturation ?? 0,
      temperature: src.temperature ?? 0,
      sharpness: (src as any).sharpness ?? 0,
      highlights: (src as any).highlights ?? 0,
      shadows: (src as any).shadows ?? 0,
      vignette: (src as any).vignette ?? 0,
      grain: (src as any).grain ?? 0,
      tint: (src as any).tint ?? 0,
      fade: (src as any).fade ?? 0,
      hue_shift: (src as any).hue_shift ?? 0,
    });
    setSelectedStyleId(style.id);
    setExpandedSections(new Set(SECTIONS));
  };

  // ── Apply style with overrides ──────────────────────────
  const handleApplyStyle = async (styleId: string) => {
    setLoading(true);
    try {
      const styleInfo = builtinStyles.find(s => s.id === styleId);
      const overrides: any = {};
      if (styleInfo) {
        for (const s of SLIDERS) {
          if (editParams[s.key] !== (styleInfo.params[s.key] ?? 0)) {
            overrides[s.key] = editParams[s.key];
          }
        }
      }
      const { data } = await axios.post('/api/v1/editing/apply', {
        image_id: imageId,
        style: styleId,
        style_overrides: Object.keys(overrides).length > 0 ? overrides : undefined,
      });
      setEditedImageId(data.edited_image_id);
      setError(null);
    } catch { setError('应用风格失败'); }
    finally { setLoading(false); }
  };

  // ── Auto enhance ────────────────────────────────────────
  const handleAutoEnhance = async () => {
    setLoading(true);
    try {
      const { data } = await axios.post('/api/v1/editing/auto-enhance', null, { params: { image_id: imageId } });
      setEditedImageId(data.edited_image_id);
      setEditParams((prev) => ({...prev, ...data.edits_applied}));
    } catch { setError('自动增强失败'); }
    finally { setLoading(false); }
  };

  // ── Apply manual edits ──────────────────────────────────
  const handleApplyEdits = async () => {
    setLoading(true);
    try {
      const { data } = await axios.post('/api/v1/editing/apply', {
        image_id: imageId,
        ...editParams,
      });
      setEditedImageId(data.edited_image_id);
    } catch { setError('应用编辑失败'); }
    finally { setLoading(false); }
  };

  // ── Save preset ─────────────────────────────────────────
  const handleSavePreset = async () => {
    if (!presetName.trim()) return;
    try {
      await axios.post('/api/v1/presets/presets', { name: presetName.trim(), ...editParams });
      setPresetName('');
      setShowSaveDialog(false);
      fetchStyles();
    } catch { setError('保存预设失败'); }
  };

  // ── Delete preset ───────────────────────────────────────
  const handleDeletePreset = async (presetId: string) => {
    try {
      await axios.delete(`/api/v1/presets/presets/${presetId}`);
      fetchStyles();
      if (selectedStyleId === presetId) { setSelectedStyleId(null); }
    } catch { setError('删除预设失败'); }
  };

  // ── Param change ────────────────────────────────────────
  const setParam = (key: ParamKey, value: number) => {
    setEditParams(prev => ({...prev, [key]: value}));
  };

  // ── Group styles ────────────────────────────────────────
  const groupedStyles: Record<string, StyleInfo[]> = {};
  for (const s of builtinStyles) {
    const cat = s.category || '其他';
    (groupedStyles[cat] ??= []).push(s);
  }
  const sortedCategories = Object.keys(groupedStyles).sort((a, b) => {
    const ai = CATEGORY_ORDER.indexOf(a), bi = CATEGORY_ORDER.indexOf(b);
    if (ai === -1 && bi === -1) return a.localeCompare(b);
    if (ai === -1) return 1; if (bi === -1) return -1;
    return ai - bi;
  });

  // ── Slider render helper ────────────────────────────────
  const renderSlider = (def: SliderDef) => (
    <div key={def.key}>
      <div className="flex justify-between mb-1">
        <label className="text-xs text-gray-600">{def.label}</label>
        <span className="text-xs text-gray-400 tabular-nums">
          {def.step < 1 ? (editParams[def.key] as number).toFixed(1) : editParams[def.key]}
        </span>
      </div>
      <input
        type="range" min={def.min} max={def.max} step={def.step}
        value={editParams[def.key]}
        onChange={(e) => setParam(def.key, parseFloat(e.target.value))}
        className="w-full h-1 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
      />
    </div>
  );

  const toggleSection = (sec: string) => {
    setExpandedSections(prev => {
      const next = new Set(prev);
      if (next.has(sec)) next.delete(sec); else next.add(sec);
      return next;
    });
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* ── Image Preview ─────────────────────────────────── */}
      <div className="lg:col-span-2">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-medium text-gray-900">图片预览</h3>
            {editedImageId && (
              <div className="flex gap-2">
                <button onClick={() => setEditedImageId(null)}
                  className="px-3 py-1.5 text-sm rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50">原图</button>
                <button onClick={() => setEditedImageId(editedImageId)}
                  className="px-3 py-1.5 text-sm rounded-lg bg-blue-600 text-white hover:bg-blue-700">编辑后</button>
              </div>
            )}
          </div>
          <div className="relative rounded-lg overflow-hidden bg-gray-100">
            <img src={`/api/v1/images/${editedImageId || imageId}`} alt="Preview" className="w-full h-auto" />
            {loading && (
              <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                <div className="flex flex-col items-center">
                  <div className="w-10 h-10 border-4 border-white border-t-transparent rounded-full animate-spin mb-2" />
                  <p className="text-white text-sm">处理中...</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Controls ───────────────────────────────────────── */}
      <div className="space-y-3">
        {/* Auto Enhance */}
        <button onClick={handleAutoEnhance} disabled={loading}
          className="w-full py-2.5 px-4 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium text-sm transition-colors disabled:opacity-50">
          {loading ? '处理中...' : '⚡ 一键自动优化'}
        </button>

        {/* Style Presets */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
          <h4 className="text-sm font-medium text-gray-700 mb-2">
            风格预设
            <span className="text-gray-400 font-normal ml-1">({builtinStyles.length + customPresets.length}种)</span>
          </h4>

          {/* Category tabs */}
          <div className="flex flex-wrap gap-1 mb-2">
            {sortedCategories.map(cat => (
              <button key={cat} onClick={() => setActiveCategory(activeCategory === cat ? null : cat)}
                className={`px-2 py-0.5 text-[11px] rounded-full transition-colors ${
                  activeCategory === cat ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}>{cat}</button>
            ))}
            {customPresets.length > 0 && (
              <button onClick={() => setActiveCategory(activeCategory === '自定义' ? null : '自定义')}
                className={`px-2 py-0.5 text-[11px] rounded-full transition-colors ${
                  activeCategory === '自定义' ? 'bg-orange-500 text-white' : 'bg-orange-50 text-orange-600 hover:bg-orange-100'
                }`}>自定义</button>
            )}
          </div>

          {/* Style grid */}
          <div className="grid grid-cols-2 gap-1 max-h-44 overflow-y-auto">
            {(activeCategory
              ? (activeCategory === '自定义'
                  ? customPresets.map(p => ({...p, category: '自定义', label_zh: p.name, description: '自定义预设', params: p} as any))
                  : groupedStyles[activeCategory] || [])
              : builtinStyles
            ).map((style: any) => (
              <button key={style.id}
                onClick={() => handleSelectStyle(style)}
                disabled={loading}
                className={`py-1.5 px-2 text-left rounded-lg transition-colors disabled:opacity-50 flex justify-between items-start ${
                  selectedStyleId === style.id
                    ? 'bg-blue-100 text-blue-800 ring-1 ring-blue-400'
                    : style.category === '自定义'
                      ? 'bg-orange-50 hover:bg-orange-100 text-orange-700'
                      : 'bg-gray-50 hover:bg-gray-100 text-gray-700'
                }`}>
                <span className="text-xs font-medium truncate">{style.label_zh}</span>
                {style.category === '自定义' && (
                  <span onClick={(e) => { e.stopPropagation(); handleDeletePreset(style.id); }}
                    className="text-gray-400 hover:text-red-500 ml-1 shrink-0 text-xs">×</span>
                )}
              </button>
            ))}
          </div>

          {selectedStyleId && (
            <button onClick={() => handleApplyStyle(selectedStyleId)} disabled={loading}
              className="w-full mt-2 py-2 px-4 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-medium transition-colors disabled:opacity-50">
              应用此风格 ✨
            </button>
          )}
        </div>

        {/* Manual Adjustments — 12 sliders in collapsible sections */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-medium text-gray-700">
              手动调整
              {selectedStyleId && (
                <span className="text-blue-500 font-normal ml-1 text-xs">
                  (基于: {builtinStyles.find(s => s.id === selectedStyleId)?.label_zh || customPresets.find(p => p.id === selectedStyleId)?.name || ''})
                </span>
              )}
            </h4>
            <button onClick={() => {
              setEditParams({...DEFAULT_PARAMS});
              setSelectedStyleId(null);
            }} className="text-xs text-gray-400 hover:text-gray-600">重置</button>
          </div>

          {/* Slider sections */}
          <div className="space-y-1">
            {SECTIONS.map(sec => {
              const sliders = SLIDERS.filter(s => s.section === sec);
              const expanded = expandedSections.has(sec);
              return (
                <div key={sec} className="border border-gray-100 rounded-lg overflow-hidden">
                  <button onClick={() => toggleSection(sec)}
                    className="w-full flex items-center justify-between px-3 py-2 bg-gray-50 hover:bg-gray-100 text-xs font-medium text-gray-600 transition-colors">
                    <span>{sec} ({sliders.map(s => s.label).join('、')})</span>
                    <span className={`transform transition-transform ${expanded ? 'rotate-180' : ''}`}>▾</span>
                  </button>
                  {expanded && (
                    <div className="px-3 py-2 space-y-3">
                      {sliders.map(renderSlider)}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Action buttons */}
          <div className="flex gap-2 mt-3">
            <button onClick={handleApplyEdits} disabled={loading}
              className="flex-1 py-2 px-4 bg-gray-900 hover:bg-gray-800 text-white rounded-lg font-medium text-sm transition-colors disabled:opacity-50">
              应用全部调整
            </button>
            <button onClick={() => setShowSaveDialog(true)} disabled={loading}
              className="py-2 px-3 bg-gray-100 hover:bg-gray-200 text-gray-600 rounded-lg transition-colors disabled:opacity-50 text-sm"
              title="保存为自定义预设">💾</button>
          </div>

          {/* Save dialog */}
          {showSaveDialog && (
            <div className="mt-3 p-3 bg-gray-50 rounded-lg border border-gray-200">
              <p className="text-xs text-gray-500 mb-2">保存当前所有参数为自定义预设</p>
              <div className="flex gap-2">
                <input type="text" value={presetName} onChange={(e) => setPresetName(e.target.value)}
                  placeholder="预设名称..." onKeyDown={(e) => { if (e.key === 'Enter') handleSavePreset(); }}
                  className="flex-1 px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-400" />
                <button onClick={handleSavePreset}
                  className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700">保存</button>
                <button onClick={() => { setShowSaveDialog(false); setPresetName(''); }}
                  className="px-3 py-1 text-sm bg-gray-200 text-gray-600 rounded hover:bg-gray-300">取消</button>
              </div>
            </div>
          )}
        </div>

        {/* Analysis Results */}
        {analysis && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 text-sm">
            <h4 className="font-medium text-gray-700 mb-2">分析结果</h4>
            <div className="space-y-1.5">
              <div className="flex justify-between"><span className="text-gray-500">场景</span><span>{analysis.scene}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">光照</span><span>{analysis.lighting}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">质量</span><span>{analysis.quality}</span></div>
              {analysis.issues?.length > 0 && (
                <div className="pt-2 mt-2 border-t border-gray-100">
                  <p className="text-amber-600 font-medium text-xs mb-1">发现的问题</p>
                  {analysis.issues.map((i: any, idx: number) => <p key={idx} className="text-gray-500 text-xs">• {i.description}</p>)}
                </div>
              )}
              {analysis.suggestions?.length > 0 && (
                <div className="pt-2 mt-2 border-t border-gray-100">
                  <p className="text-green-600 font-medium text-xs mb-1">优化建议</p>
                  {analysis.suggestions.map((s: string, idx: number) => <p key={idx} className="text-gray-500 text-xs">• {s}</p>)}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {error && (
        <div className="lg:col-span-3 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">{error}</div>
      )}
    </div>
  );
};

export default ImageEditor;
