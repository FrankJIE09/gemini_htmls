#!/usr/bin/env node
/**
 * Expands shanghai_wutong_streets.html to downtown 6 districts + calibrates landmarks.
 * Usage: node scripts/expand_wutong_downtown.js
 */
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const HTML_PATH = path.join(ROOT, 'shanghai_wutong_streets.html');
const OSM_PATH = process.env.OSM_JSON || '/tmp/sh_downtown2.json';

/** 明确列入精品/主干的道路（含原梧桐区36条 + 六区重要马路） */
const MAJOR_ROADS = new Set([
  // 黄浦 / 外滩 / 人民广场
  '南京东路', '南京西路', '南京中路', '福州路', '广东路', '山东中路', '山东南路',
  '九江路', '汉口路', '河南中路', '河南南路', '人民大道', '西藏中路', '西藏南路',
  '延安东路', '金陵东路', '金陵中路', '金陵西路', '淮海东路', '黄陂南路', '马当路',
  '中山南路', '中山二路', '陆家浜路', '外马路', '会馆街', '方浜中路',
  // 静安
  '北京西路', '北京东路', '新闸路', '江宁路', '陕西北路', '石门一路', '石门二路',
  '成都北路', '成都南路', '威海路', '茂名北路', '泰兴路', '铜仁路', '常德路',
  '胶州路', '康定路', '西康路', '武定路', '万航渡路', '华山路', '愚园路', '静安寺路',
  // 徐汇 / 衡复延伸
  '淮海中路', '复兴中路', '复兴西路', '复兴东路', '肇嘉浜路', '斜土路', '中山南二路',
  '天钥桥路', '漕溪北路', '漕溪南路', '东安路', '宛平路', '衡山路', '岳阳路', '桃江路',
  '嘉善路', '打浦路', '瑞金南路', '瑞金二路', '陕西南路', '茂名南路', '襄阳南路', '襄阳北路',
  '永康路', '太原路', '建国西路', '建国中路', '建国东路', '龙华中路', '龙华西路',
  '东平路', '康平路', '武康路', '安福路', '五原路', '乌鲁木齐路', '湖南路', '兴国路',
  '天平路', '余庆路', '高安路', '东湖路', '汾阳路', '宝庆路', '延庆路', '永嘉路',
  '思南路', '思贤路', '香山路', '皋兰路', '瑞金一路', '陕西南路', '镇宁路', '武定西路',
  // 长宁
  '延安西路', '虹桥路', '长宁路', '定西路', '凯旋路', '凯旋北路', '凯旋南路',
  '江苏路', '愚园路', '安化路', '武夷路', '昭化路', '法华镇路', '宋园路', '虹桥路',
  // 虹口 / 北外滩
  '四川北路', '四川中路', '山阴路', '霍山路', '东大名路', '东长治路', '杨树浦路',
  '大连路', '曲阳路', '海宁路', '天潼路', '塘沽路', '长治路', '东余杭路', '东汉阳路',
  '周家嘴路', '四平路', '临平路', '飞虹路', '瑞虹路',
  // 普陀
  '长寿路', '武宁路', '曹杨路', '中山北路', '中潭路', '光复西路', '光复路', '北苏州路', '南苏州路',
  '武宁南路', '真北路', '铜川路', '兰溪路', '枣阳路', '大渡河路',
  // 其他骨架
  '延安中路', '西藏北路', '河南北路', '天目西路', '天目东路', '恒丰路', '普济路',
  '重庆南路', '重庆北路', '西藏南路', '局门路', '蒙自路', '鲁班路', '中山南一路',
  '徐家汇路', '陆家浜路', '中华路', '中华新路', '交通路', '光启南路', '枫林路',
  '医学院路', '零陵路', '大木桥路', '小木桥路', '瞿溪路', '鲁班路', '南车站路',
  '淡水路', '金陵中路', '金陵西路', '金陵东路', '人民路', '福佑路', '城隍庙路',
  '武胜路', '北苏州路', '南苏州路', '新会路', '安远路', '西苏州路',
  '巨鹿路', '长乐路', '富民路', '常熟路', '乌鲁木齐中路', '乌鲁木齐北路', '乌鲁木齐南路',
  '绍兴路', '南昌路', '永嘉路', '永康路', '泰安路', '华亭路', '淮海中路',
  '陕西南路', '瑞金二路', '茂名南路', '思南路', '雁荡路', '南昌路', '重庆南路',
]);

const SERVICE_SKIP_RE = /停车场|停车库|枢纽|地下车库|卸货|消防|通道$|匝道|立交/;
const PUDONG_RE = /陆家嘴|世纪大道|浦东南|浦东大道|花木路|芳甸路|张杨路|东方路|世博/;
/** 里弄/支弄（名称含「弄」）不收录 */
const LONGTANG_RE = /弄/;

function isLongTangName(name) {
  return LONGTANG_RE.test(name);
}

function pathSpan(path) {
  let minLat = 99, maxLat = -99, minLng = 999, maxLng = -999;
  for (const [la, lo] of path) {
    if (la < minLat) minLat = la;
    if (la > maxLat) maxLat = la;
    if (lo < minLng) minLng = lo;
    if (lo > maxLng) maxLng = lo;
  }
  return Math.max(maxLat - minLat, maxLng - minLng);
}

function isFeaturedStreet(street, hw) {
  if (street.origin) return true;
  if (MAJOR_ROADS.has(street.name)) return true;
  const span = pathSpan(street.path);
  if (['primary', 'secondary', 'trunk', 'trunk_link', 'primary_link', 'secondary_link'].includes(hw)) {
    return true;
  }
  if (hw === 'tertiary' && span >= 0.0028) return true;
  // 较长骨干马路（不含里弄），补充未列入名单的重要路段
  if (span >= 0.0045 && /[路街道]$/.test(street.name) && !/弄$/.test(street.name)) return true;
  return false;
}

function shouldIncludeOsmName(name, hw) {
  if (isLongTangName(name)) return false;
  if (hw === 'service') return false;
  if (SERVICE_SKIP_RE.test(name)) return false;
  return true;
}

const html = fs.readFileSync(HTML_PATH, 'utf8');
const streetsMatch = html.match(/const STREETS = (\[[\s\S]*?\n    \]);/);
if (!streetsMatch) throw new Error('STREETS block not found');
const STREETS = eval(streetsMatch[1]);

function isPudongStreet(s) {
  if (PUDONG_RE.test(s.name)) return true;
  const mid = s.path[Math.floor(s.path.length / 2)];
  return mid && mid[1] > 121.496;
}
const STREETS_BASE = STREETS.filter((s) => !isPudongStreet(s) && !isLongTangName(s.name));
const existingByName = new Map(STREETS_BASE.map((s) => [s.name, s]));

const osm = JSON.parse(fs.readFileSync(OSM_PATH, 'utf8'));
const ways = osm.elements.filter((e) => e.type === 'way' && e.tags?.name && e.geometry);

function cleanName(n) {
  return n.replace(/\(.*?\)/g, '').replace(/（.*?）/g, '').trim();
}

function simplify(path, maxPts = 22) {
  if (path.length <= maxPts) return path;
  const out = [path[0]];
  const step = (path.length - 1) / (maxPts - 1);
  for (let i = 1; i < maxPts - 1; i++) out.push(path[Math.round(i * step)]);
  out.push(path[path.length - 1]);
  return out;
}

function pathType(path) {
  let minLat = 99, maxLat = -99, minLng = 999, maxLng = -999;
  for (const [la, lo] of path) {
    if (la < minLat) minLat = la;
    if (la > maxLat) maxLat = la;
    if (lo < minLng) minLng = lo;
    if (lo > maxLng) maxLng = lo;
  }
  const dLat = maxLat - minLat;
  const dLng = maxLng - minLng;
  return dLng > dLat * 1.12 ? 'horizontal' : dLat > dLng * 1.12 ? 'vertical' : dLng >= dLat ? 'horizontal' : 'vertical';
}

function classifySubArea(lat, lng) {
  if (lng >= 121.475 && lat >= 31.218) return 'huangpu';
  if (lng >= 121.468 && lat >= 31.252) return 'hongkou';
  if (lat >= 31.252 && lng < 121.43) return 'putuo';
  if (lat >= 31.248 && lng >= 121.43 && lng < 121.475) return 'jingan';
  if (lng < 121.415) return 'changning';
  if (lat < 31.208) return 'xuhui';
  if (lng >= 121.462 && lat < 31.218) return 'shannan';
  if (lng >= 121.452 && lat >= 31.218) return 'jufu';
  if (lat >= 31.205 && lng >= 121.44 && lng < 121.455) return 'music';
  if (lng < 121.44) return 'wukang';
  return 'jingan';
}

const subAreaLabel = {
  xuhui: '徐汇', changning: '长宁', jingan: '静安', huangpu: '黄浦',
  hongkou: '虹口', putuo: '普陀', wukang: '衡复西片', jufu: '巨富长',
  music: '衡山音乐', shannan: '思南公馆',
};

const byName = new Map();
for (const w of ways) {
  const name = cleanName(w.tags.name);
  if (isLongTangName(name)) continue;
  if (!/[\u4e00-\u9fff]/.test(name)) continue;
  if (/高速|隧道|立交|匝道|入口|出口|辅路|内环|中环|高架|引桥/.test(name)) continue;
  if (PUDONG_RE.test(name)) continue;
  const path = w.geometry.map((g) => [+g.lat.toFixed(6), +g.lon.toFixed(6)]);
  if (path.length < 2) continue;
  const westRatio = path.filter((p) => p[1] < 121.495).length / path.length;
  if (westRatio < 0.85) continue; // 剔除浦东为主的路段
  const avgLng = path.reduce((s, p) => s + p[1], 0) / path.length;
  if (avgLng > 121.496) continue;
  const prev = byName.get(name);
  if (!shouldIncludeOsmName(name, w.tags.highway)) continue;
  if (!prev || path.length > prev.path.length) {
    byName.set(name, { path, osmId: w.id, hw: w.tags.highway });
  }
}

function applyFeatured(street, hw) {
  const featured = isFeaturedStreet(street, hw || 'residential');
  const sub = subAreaLabel[street.subArea] || '市中心';
  if (featured && !street.origin) {
    if (/风貌区支路|中心城区支路/.test(street.desc || '')) {
      street.desc = `上海中心城区${sub}片区重要道路。${street.name}是认路骨架或历史街巷。`;
      street.mnemonic = `${street.name}：在地图上辨认其与周边主干道的交汇与走向。`;
      street.tag = '中心城区主干道';
    }
  }
  street.featured = featured;
  return street;
}

let idn = 92000;
const merged = STREETS_BASE.map((s) => {
  const osm = byName.get(s.name);
  return applyFeatured({ ...s }, osm?.hw);
});

for (const [name, data] of byName) {
  if (existingByName.has(name)) continue;
  let path = simplify(data.path);
  const span = pathSpan(path);
  if (span < 0.00035) continue;
  const mid = path[Math.floor(path.length / 2)];
  const subArea = classifySubArea(mid[0], mid[1]);
  const draft = {
    id: `r_${idn++}`,
    name,
    type: pathType(path),
    subArea,
    featured: false,
    desc: `上海中心城区（${subAreaLabel[subArea] || '市中心'}）内的${name}。点击可查看 OSM 测绘折线走向。`,
    mnemonic: '沿 OSM 测绘折线在地图上辨认其与周边主干的相对位置。',
    path,
    landmarks: [],
    tag: '中心城区支路',
  };
  merged.push(applyFeatured(draft, data.hw));
}

const LANDMARKS_INFO = require('./landmarks_downtown.js');

function formatCoord(n) {
  return Number(n).toFixed(6).replace(/\.?0+$/, (m, offset) => (offset ? '' : n));
}

function serializeStreet(s, indent = '        ') {
  const lines = [
    `${indent}{`,
    `${indent}    id: '${s.id}',`,
    `${indent}    name: '${s.name.replace(/'/g, "\\'")}',`,
    `${indent}    type: '${s.type}',`,
    `${indent}    subArea: '${s.subArea}',`,
    `${indent}    featured: ${s.featured},`,
    `${indent}    desc: '${(s.desc || '').replace(/'/g, "\\'")}',`,
    `${indent}    mnemonic: '${(s.mnemonic || '').replace(/'/g, "\\'")}',`,
  ];
  if (s.origin) lines.push(`${indent}    origin: '${s.origin.replace(/'/g, "\\'")}',`);
  lines.push(`${indent}    path: [`);
  for (const [la, lo] of s.path) {
    lines.push(`${indent}        [${la}, ${lo}],`);
  }
  lines.push(`${indent}    ],`);
  lines.push(`${indent}    landmarks: ${JSON.stringify(s.landmarks || [])},`);
  lines.push(`${indent}    tag: '${(s.tag || '').replace(/'/g, "\\'")}'`);
  lines.push(`${indent}},`);
  return lines.join('\n');
}

function escLm(s) {
  return String(s).replace(/\\/g, '\\\\').replace(/'/g, "\\'");
}

function serializeLandmarks() {
  const lines = ['    const LANDMARKS_INFO = {'];
  for (const [key, lm] of Object.entries(LANDMARKS_INFO)) {
    lines.push(`        ${key}: {`);
    lines.push(`            name: '${escLm(lm.name)}',`);
    lines.push(`            category: '${lm.category}',`);
    lines.push(`            coords: [${lm.coords[0]}, ${lm.coords[1]}],`);
    lines.push(`            desc: '${escLm(lm.desc)}',`);
    lines.push(`            mnemonic: '${escLm(lm.mnemonic)}',`);
    lines.push(`            icon: '${lm.icon}'`);
    lines.push(`        },`);
  }
  lines.push('    };');
  return lines.join('\n');
}

const streetsBlock = `    const STREETS = [\n${merged.map((s) => serializeStreet(s)).join('\n')}\n    ];`;
let out = html.replace(/const STREETS = \[[\s\S]*?\n    \];/, streetsBlock);
out = out.replace(/const LANDMARKS_INFO = \{[\s\S]*?\n    \};/, serializeLandmarks());

const total = merged.length;
const featured = merged.filter((s) => s.featured).length;
const ew = merged.filter((s) => s.type === 'horizontal').length;
const ns = merged.filter((s) => s.type === 'vertical').length;

// Header / copy updates
out = out.replace(/市中心\d+路标注/g, `市中心${total}路标注`);
out = out.replace(/标注<b>\d+条具名道路<\/b>（\d+条[^）]+）/g, `标注<b>${total}条具名道路</b>（${featured}条精品/主干 + ${total - featured}条支路）`);
out = out.replace(/衡复历史风貌区（法租界旧址核心圈）/g, '上海中心城区（徐汇·长宁·静安·黄浦·虹口·普陀主要片区，含衡复风貌区）');
out = out.replace(/市中心\d+条马路/g, `市中心${total}条马路`);
out = out.replace(/默认显示\d+条主干道\/精品路/g, `默认显示${featured}条精品/主干`);
out = out.replace(/可查找全部\d+条/g, `可查找全部${total}条`);
out = out.replace(/↔️ 东西走向 \(共 \d+ 条\)/g, `↔️ 东西走向 (共 ${ew} 条)`);
out = out.replace(/↕️ 南北走向 \(共 \d+ 条\)/g, `↕️ 南北走向 (共 ${ns} 条)`);
out = out.replace(/map\.getZoom\(\) >= 16/g, 'map.getZoom() >= 15');
// 分级显示路名：精品/主干≥14级；支路≥15级（含原36条详解路）
if (!out.includes('shouldShowRoadLabel')) {
  out = out.replace(
    /function updateRoadLabelVisibility\(\) \{[\s\S]*?\n    \}/,
    `function shouldShowRoadLabel(road) {
        const z = map.getZoom();
        if (road.featured && z >= 14) return true;
        if (!road.featured && z >= 15) return true;
        return false;
    }

    function updateRoadLabelVisibility() {
        Object.values(roadLayers).forEach(layer => {
            if (!layer.tooltip) return;
            const el = layer.tooltip.getElement();
            if (!el) return;
            const show = shouldShowRoadLabel(layer.road);
            el.style.display = show ? '' : 'none';
            if (layer.road.featured && layer.road.type === 'vertical' && show) {
                el.style.zIndex = '700';
            }
        });
    }`
  );
  out = out.replace(
    'permanent: road.featured,',
    'permanent: true,'
  );
}
out = out.replace(/放大至 16 级以上/g, '放大至 15 级以上');
out = out.replace(/放大至16级/g, '放大至15级');
out = out.replace(/地图<b>放大至16级<\/b>/g, '地图<b>放大至15级</b>');
out = out.replace(/上海梧桐区全域认路记忆宝典/g, '上海中心城区认路记忆宝典');
out = out.replace(/🍂 上海梧桐区全域认路神器/g, '🍂 上海中心城区认路神器');
out = out.replace(/🗺️ 梧桐区地理骨架（高精测绘数据）/g, '🗺️ 市中心地理骨架（高精测绘数据）');
out = out.replace(/衡复风貌区全图四象限认路法/g, '市中心六区认路分区');
out = out.replace(/上海衡复风貌区认路记忆指南/g, '上海中心城区认路记忆指南');
out = out.replace(/渲染 10 大物理地标/g, `渲染 ${Object.keys(LANDMARKS_INFO).length} 大文化地标`);

// Map init
out = out.replace(
  /center: \[[\d.]+, [\d.]+\],\s*\n\s*zoom: \d+,\s*\n\s*minZoom: \d+,\s*\n\s*maxZoom: 18,/,
  'center: [31.232, 121.455],\n            zoom: 13,\n            minZoom: 12,\n            maxZoom: 18,'
);
out = out.replace(/h-\[580px\]/, 'h-[620px]');
out = out.replace(/设置地图中心在衡复风貌区核心.*/, '设置地图中心为市中心六区视野');

// Sub-area filter buttons
const subAreaButtons = `                <div class="flex flex-wrap gap-1">
                    <button onclick="filterBySubArea('all')" class="sub-area-btn px-2 py-1 bg-gray-200 hover:bg-gray-300 text-gray-800 rounded text-[10px] font-semibold transition">全部</button>
                    <button onclick="filterBySubArea('wukang')" class="sub-area-btn px-2 py-1 bg-white hover:bg-gray-100 text-gray-700 border border-gray-300 rounded text-[10px] transition">衡复西片</button>
                    <button onclick="filterBySubArea('jufu')" class="sub-area-btn px-2 py-1 bg-white hover:bg-gray-100 text-gray-700 border border-gray-300 rounded text-[10px] transition">巨富长</button>
                    <button onclick="filterBySubArea('music')" class="sub-area-btn px-2 py-1 bg-white hover:bg-gray-100 text-gray-700 border border-gray-300 rounded text-[10px] transition">衡山音乐</button>
                    <button onclick="filterBySubArea('shannan')" class="sub-area-btn px-2 py-1 bg-white hover:bg-gray-100 text-gray-700 border border-gray-300 rounded text-[10px] transition">思南公馆</button>
                    <button onclick="filterBySubArea('xuhui')" class="sub-area-btn px-2 py-1 bg-white hover:bg-gray-100 text-gray-700 border border-gray-300 rounded text-[10px] transition">徐汇</button>
                    <button onclick="filterBySubArea('changning')" class="sub-area-btn px-2 py-1 bg-white hover:bg-gray-100 text-gray-700 border border-gray-300 rounded text-[10px] transition">长宁</button>
                    <button onclick="filterBySubArea('jingan')" class="sub-area-btn px-2 py-1 bg-white hover:bg-gray-100 text-gray-700 border border-gray-300 rounded text-[10px] transition">静安</button>
                    <button onclick="filterBySubArea('huangpu')" class="sub-area-btn px-2 py-1 bg-white hover:bg-gray-100 text-gray-700 border border-gray-300 rounded text-[10px] transition">黄浦</button>
                    <button onclick="filterBySubArea('hongkou')" class="sub-area-btn px-2 py-1 bg-white hover:bg-gray-100 text-gray-700 border border-gray-300 rounded text-[10px] transition">虹口</button>
                    <button onclick="filterBySubArea('putuo')" class="sub-area-btn px-2 py-1 bg-white hover:bg-gray-100 text-gray-700 border border-gray-300 rounded text-[10px] transition">普陀</button>
                </div>`;
out = out.replace(
  /<div class="flex flex-wrap gap-1">[\s\S]*?<button onclick="filterBySubArea\('shannan'\)"[\s\S]*?<\/div>/,
  subAreaButtons
);

// Six-district summary panel
const districtPanel = `            <div class="space-y-2 text-xs">
                <div class="p-2.5 bg-white rounded-lg border border-gray-200">
                    <span class="font-bold text-[#1F402B]">徐汇</span>
                    <p class="text-gray-600 mt-1">徐家汇—肇嘉浜—衡山路南翼。天钥桥路、漕溪北路、东安路纵贯，淮海中路、复兴中路横贯。</p>
                </div>
                <div class="p-2.5 bg-white rounded-lg border border-gray-200">
                    <span class="font-bold text-[#1F402B]">长宁</span>
                    <p class="text-gray-600 mt-1">中山公园—虹桥路—愚园路。定西路、凯旋路、华山路与延安西路构成西部网格。</p>
                </div>
                <div class="p-2.5 bg-white rounded-lg border border-gray-200">
                    <span class="font-bold text-[#1F402B]">静安</span>
                    <p class="text-gray-600 mt-1">静安寺—南京西路—江宁路。南北向常熟路、陕西北路与东西向北京西路、新闸路交汇。</p>
                </div>
                <div class="p-2.5 bg-white rounded-lg border border-gray-200">
                    <span class="font-bold text-[#1F402B]">黄浦</span>
                    <p class="text-gray-600 mt-1">人民广场—外滩—金陵东路。南京东路、福州路、延安东路与河南中路、西藏中路构成方格网。</p>
                </div>
                <div class="p-2.5 bg-white rounded-lg border border-gray-200">
                    <span class="font-bold text-[#1F402B]">虹口</span>
                    <p class="text-gray-600 mt-1">四川北路—山阴路—霍山路。四川北路纵轴串联北外滩与鲁迅公园片区。</p>
                </div>
                <div class="p-2.5 bg-white rounded-lg border border-gray-200">
                    <span class="font-bold text-[#1F402B]">普陀</span>
                    <p class="text-gray-600 mt-1">长寿路—曹杨路—武宁路。苏州河以南西段，光复路与长寿路构成商业横轴。</p>
                </div>
                <div class="p-2.5 bg-amber-50 rounded-lg border border-amber-200">
                    <span class="font-bold text-[#1F402B]">衡复风貌区（核心）</span>
                    <p class="text-gray-600 mt-1">武康路半月弯、巨富长、思南公馆、衡山音乐街区仍为本图精细标注核心区；📚🎻 地标已按 OSM/Wikipedia 坐标校准。</p>
                </div>
            </div>`;
out = out.replace(
  /<div class="space-y-2 text-xs">[\s\S]*?<\/div>\s*\n\s*<\/div>\s*\n\s*<\/section>/,
  `${districtPanel}\n        </div>\n    </section>`
);

// Fit map to all streets on load
if (!out.includes('fitBoundsOnLoad')) {
  out = out.replace(
    '        map.on(\'zoomend\', updateRoadLabelVisibility);\n        updateRoadLabelVisibility();\n    }',
    `        map.on('zoomend', updateRoadLabelVisibility);
        updateRoadLabelVisibility();
        const allCoords = STREETS.flatMap(r => r.path);
        map.fitBounds(L.latLngBounds(allCoords), { padding: [30, 30], maxZoom: 14 });
    }`
  );
}

fs.writeFileSync(HTML_PATH, out);
console.log('Updated', HTML_PATH);
console.log('Total streets:', total, 'featured:', featured, 'ew:', ew, 'ns:', ns);
console.log('Landmarks:', Object.keys(LANDMARKS_INFO).length);
