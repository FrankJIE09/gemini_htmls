#!/usr/bin/env node
/**
 * 用 Nominatim（带门牌地址）校准 landmarks_downtown.js
 */
const fs = require('fs');
const path = require('path');

const landmarks = require('./landmarks_downtown.js');

/** key -> 精确检索词（含地址可提高命中率） */
const QUERIES = {
  wukang_mansion: '武康大楼 淮海中路1850号 上海',
  sh_library: '上海图书馆 淮海中路1555号 上海',
  jingan_temple: '静安寺 南京西路1686号 上海',
  people_square: '人民广场 上海',
  sinan_mansion: '思南公馆 思南路 上海',
  blackstone: '黑石公寓 复兴中路1331号 上海',
  sun_residence: '上海孙中山故居纪念馆 思南路7号 上海',
  pushkin_statue: '普希金纪念碑 岳阳路 上海',
  sh_symphony_hall: '上海交响乐团音乐厅 复兴中路1380号 上海',
  sh_concert_hall: '上海音乐厅 延安东路523号 上海',
  symphony_museum: '交响音乐博物馆 宝庆路3号 上海',
  sh_music: '上海音乐学院 汾阳路20号 上海',
  heluting_hall: '贺绿汀音乐厅 汾阳路 上海',
  shcm_opera_house: '上音歌剧院 汾阳路6号 上海',
  oriental_art_center: '东方艺术中心 丁香路425号 上海',
  sh_grand_theatre: '上海大剧院 人民大道300号 上海',
  lanxin_theatre: '兰心大戏院 黄浦区 上海',
  meigi_theatre: '美琪大戏院 江宁路190号 上海',
  china_theatre: '中国大戏院 牛庄路704号 上海',
  yifu_theatre: '天蟾逸夫舞台 福州路701号 上海',
  saic_culture: '上海文化广场 复兴中路597号 上海',
  yihaoli_theatre: '艺海剧院 铜仁路220号 上海',
  sh_museum: '上海博物馆 人民大道201号 上海',
  drama_center: '上海话剧艺术中心 安福路288号 上海',
  sh_arts_theatre: '上海大剧院 人民大道300号 上海',
  urban_theatre: '上海城市剧院 人民大道 上海',
  xiju_art_center: '上海喜剧艺术中心 复兴中路 上海',
  dramaland: '共舞台 凤阳路310号 上海',
  iapm: '环贸广场 淮海中路999号 上海',
  plaza66: '港汇恒隆广场 虹桥路1号 上海',
  metro_city: '美罗城 肇嘉浜路1111号 上海',
  xujiahui: '徐家汇 上海',
  jiuguang: '久光百货 南京西路1618号 上海',
  plaza66_jingan: '恒隆广场 南京西路1266号 上海',
  kerry_centre: '静安嘉里中心 南京西路1515号 上海',
  taikoo_hui: '兴业太古汇 南京西路789号 上海',
  newworld: '新世界城 南京西路2号 上海',
  raffles_city: '来福士广场 西藏中路268号 上海',
  xintiandi: '上海新天地 兴业路 上海',
  ruijin_sun: '日月光中心 泰康路210号 上海',
  joycity: '静安大悦城 西藏北路166号 上海',
  longemont: '龙之梦购物中心 长宁路1018号 上海',
  first_department: '第一百货 南京东路830号 上海',
  julu758: '巨鹿路758号 上海',
  hongkou_football: '虹口足球场 东江湾路444号 上海',
  sh_stadium: '上海体育馆 漕溪北路1111号 上海',
  luwan_gym: '卢湾体育馆 肇嘉浜路128号 上海',
  jingan_gym: '静安体育馆 南京西路758号 上海',
};

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function nominatim(q) {
  const url =
    'https://nominatim.openstreetmap.org/search?' +
    new URLSearchParams({ q, format: 'json', limit: '1', countrycodes: 'cn' });
  const res = await fetch(url, {
    headers: { 'User-Agent': 'gemini-htmls-landmark-geocode/1.0' },
  });
  const data = await res.json();
  return data[0] || null;
}

async function main() {
  const updates = {};
  const keys = Object.keys(landmarks);
  for (const key of keys) {
    const q = QUERIES[key] || `${landmarks[key].name} 上海`;
    process.stderr.write(`${key}: ${q}\n`);
    const hit = await nominatim(q);
    if (hit) {
      updates[key] = [+(+hit.lat).toFixed(6), +(+hit.lon).toFixed(6)];
      process.stderr.write(`  -> ${updates[key]}\n`);
    } else {
      process.stderr.write(`  -> NOT FOUND (keep old)\n`);
    }
    await sleep(1100);
  }
  fs.writeFileSync(path.join(__dirname, 'geocode_results.json'), JSON.stringify(updates, null, 2));
  console.log('Wrote geocode_results.json,', Object.keys(updates).length, 'hits');
}

main();
