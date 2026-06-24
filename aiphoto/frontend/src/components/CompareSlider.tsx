import ImageSlider from 'react-image-comparison-slider';
// 注：该包的 css 已内联打包进 dist/index.js（style-loader），无需单独 import

interface CompareSliderProps {
  before: string; // 原图 URL
  after: string;  // 修图后 URL
  onClose: () => void;
}

/**
 * 全屏 before/after 对比滑块。
 * 使用 react-image-comparison-slider（项目已装的包）。
 * 左侧 = 原图，右侧 = 修图后，拖动分隔线对比。
 */
const CompareSlider: React.FC<CompareSliderProps> = ({ before, after, onClose }) => {
  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.9)', zIndex: 9999,
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        cursor: 'pointer', padding: 24,
      }}
    >
      {/* 顶部标签 + 关闭 */}
      <div style={{ alignSelf: 'stretch', display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, color: '#fff' }}>
        <div style={{ display: 'flex', gap: 24, fontSize: 13, fontWeight: 500 }}>
          <span>◀ 原图</span>
          <span>修图后 ▶</span>
        </div>
        <button
          onClick={(e) => { e.stopPropagation(); onClose(); }}
          style={{
            background: 'rgba(255,255,255,0.15)', border: 'none', color: '#fff',
            width: 32, height: 32, borderRadius: '50%', cursor: 'pointer', fontSize: 16,
          }}
        >×</button>
      </div>

      {/* 滑块容器 */}
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          maxWidth: 'min(90vw, 1100px)', width: '100%', height: 'min(72vh, 700px)',
          borderRadius: 12, overflow: 'hidden', boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
          cursor: 'default',
        }}
      >
        <ImageSlider
          image1={before}
          image2={after}
          alt1="原图"
          alt2="修图后"
          sliderColor="#2563eb"
          sliderWidth={3}
          leftLabelText="原图"
          rightLabelText="修图后"
          showPlaceholder
        />
      </div>

      <p style={{ color: 'rgba(255,255,255,0.6)', fontSize: 12, marginTop: 12 }}>
        拖动中间分隔线对比前后效果 · 点击空白处关闭
      </p>
    </div>
  );
};

export default CompareSlider;
