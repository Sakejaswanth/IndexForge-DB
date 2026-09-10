import React, { useState, useRef, useEffect, useCallback } from 'react';

const API = import.meta.env.VITE_API_URL || '';

const fontLink = document.createElement('link');
fontLink.rel = 'stylesheet';
fontLink.href = 'https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;700&family=Bebas+Neue&display=swap';
document.head.appendChild(fontLink);

const style = document.createElement('style');
style.textContent = `
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg:#060708; --surface:#0c0e12; --surface2:#14171d;
    --border:#1a1f28; --border2:#252c38; --text:#dce2ec;
    --muted:#5a657a; --accent:#00e5a0; --red:#ff3d6b;
    --blue:#3d9bff; --yellow:#ffb830; --purple:#b06cff; --orange:#ff8c42;
    --mono:'IBM Plex Mono',monospace; --display:'Bebas Neue',sans-serif;
  }
  html, body { height:100%; overflow:hidden; background:var(--bg); color:var(--text); font-family:var(--mono); }
  body::after { content:''; position:fixed; inset:0; pointer-events:none; z-index:9999;
    background:repeating-linear-gradient(0deg,transparent,transparent 3px,rgba(0,0,0,.04) 3px,rgba(0,0,0,.04) 4px); }

  #root { display:flex; flex-direction:column; height:100vh; overflow:hidden; }

  .header { flex:0 0 auto; border-bottom:1px solid var(--border); padding:11px 28px;
    display:flex; align-items:center; gap:14px;
    background:linear-gradient(180deg,#0e1016 0%,var(--bg) 100%); }
  .header-dot { width:9px; height:9px; border-radius:50%; background:var(--accent);
    box-shadow:0 0 10px var(--accent); animation:blink 2.4s ease-in-out infinite; }
  @keyframes blink{0%,100%{opacity:1}50%{opacity:.4}}
  .header-title { font-family:var(--display); font-size:20px; letter-spacing:2px; }
  .header-sub { font-size:10px; color:var(--muted); letter-spacing:2px; text-transform:uppercase; margin-left:auto; }

  .tabs { flex:0 0 auto; display:flex; border-bottom:1px solid var(--border); padding:0 28px; background:var(--surface); }
  .tab { padding:10px 18px; font-family:var(--mono); font-size:11px; letter-spacing:1px; text-transform:uppercase;
    color:var(--muted); cursor:pointer; border:none; background:none; border-bottom:2px solid transparent;
    transition:all .2s; position:relative; top:1px; }
  .tab:hover { color:var(--text); }
  .tab.active { color:var(--accent); border-bottom-color:var(--accent); }

  .page-body { flex:1 1 0; min-height:0; display:flex; overflow:hidden; }

  .panel-left { flex:0 0 300px; min-width:0; min-height:0; padding:16px 18px;
    border-right:1px solid var(--border); overflow-y:auto;
    display:flex; flex-direction:column; gap:12px; }

  .panel-right { flex:1 1 0; min-width:0; min-height:0; padding:16px 20px;
    overflow-y:auto; display:flex; flex-direction:column; gap:14px; }

  .panel-2d-left { flex:0 0 auto; min-height:0; padding:18px 20px; border-right:1px solid var(--border);
    display:flex; flex-direction:column; gap:12px; overflow:hidden; }
  .panel-2d-right { flex:1 1 0; min-width:0; min-height:0; padding:18px 20px;
    overflow-y:auto; display:flex; flex-direction:column; gap:14px; }

  .panel-about { flex:1 1 0; min-height:0; padding:28px 36px; overflow-y:auto; }

  .card { background:var(--surface); border:1px solid var(--border); border-radius:8px; padding:14px; }
  .card-title { font-size:9px; color:var(--muted); letter-spacing:3px; text-transform:uppercase; margin-bottom:10px; }
  .section-head { font-size:9px; color:var(--muted); letter-spacing:3px; text-transform:uppercase;
    border-bottom:1px solid var(--border); padding-bottom:7px; flex-shrink:0; }

  canvas { display:block; border:1px solid var(--border2); cursor:crosshair; border-radius:4px; }
  .canvas-wrap { position:relative; display:inline-block; flex-shrink:0; }
  .canvas-overlay { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; pointer-events:none; }
  .canvas-hint { font-size:11px; color:var(--muted); background:rgba(6,7,8,.88); padding:8px 16px; border-radius:4px; border:1px solid var(--border2); }

  .slider-row { display:flex; align-items:center; gap:12px; flex-shrink:0; }
  .slider-label { font-size:12px; color:var(--accent); font-weight:700; min-width:50px; }
  input[type=range] { -webkit-appearance:none; height:2px; background:var(--border2); border-radius:2px; width:150px; outline:none; }
  input[type=range]::-webkit-slider-thumb { -webkit-appearance:none; width:12px; height:12px; border-radius:50%; background:var(--accent); cursor:pointer; box-shadow:0 0 8px var(--accent); }

  .race-row { margin-bottom:10px; }
  .race-row-header { display:flex; justify-content:space-between; align-items:baseline; margin-bottom:4px; }
  .race-name { font-size:10px; color:var(--muted); letter-spacing:1px; text-transform:uppercase; }
  .race-time { font-size:17px; font-weight:700; }
  .race-bar-bg { height:4px; background:var(--border); border-radius:3px; overflow:hidden; }
  .race-bar { height:100%; border-radius:3px; transition:width .8s cubic-bezier(.16,1,.3,1); }

  .upload-zone { border:2px dashed var(--border2); border-radius:10px; padding:20px 14px;
    text-align:center; cursor:pointer; transition:all .2s; position:relative;
    background:var(--surface); flex-shrink:0; }
  .upload-zone:hover,.upload-zone.drag-over { border-color:var(--accent); background:rgba(0,229,160,.04); }
  .upload-zone input[type=file] { position:absolute; inset:0; opacity:0; cursor:pointer; width:100%; height:100%; }
  .upload-icon { font-size:26px; margin-bottom:6px; display:block; }
  .upload-title { font-family:var(--display); font-size:17px; letter-spacing:1px; margin-bottom:3px; }
  .upload-sub { font-size:10px; color:var(--muted); }

  @keyframes prog{from{width:0%}to{width:90%}}
  .loading-bar { height:2px; background:var(--accent); border-radius:1px; animation:prog 3s ease-out forwards; box-shadow:0 0 8px var(--accent); }

  /* Performance table */
  table { width:100%; border-collapse:collapse; font-size:11px; }
  th { padding:6px 10px; text-align:left; color:var(--muted); font-weight:400;
    border-bottom:1px solid var(--border2); text-transform:uppercase; letter-spacing:1px; font-size:10px; }
  td { padding:7px 10px; border-bottom:1px solid var(--border); vertical-align:middle; }

  /* ── Neighbor block ── */
  .neighbor-block { border:1px solid var(--border); border-radius:8px; overflow:hidden; margin-bottom:4px; flex-shrink:0; }
  .neighbor-scroll { max-height:480px; overflow-y:auto; }
  .neighbor-block-hdr { padding:8px 14px; background:var(--surface2);
    display:flex; justify-content:space-between; align-items:center;
    font-size:9px; color:var(--muted); letter-spacing:2px; text-transform:uppercase; }

  /* Audio neighbor row */
  .neighbor-row-audio { display:flex; align-items:center; gap:10px; padding:10px 14px;
    border-top:1px solid var(--border); background:var(--bg); }
  .neighbor-rank { font-family:var(--display); font-size:18px; min-width:22px; flex-shrink:0; }
  .neighbor-info { flex:1 1 0; min-width:0; }
  .neighbor-label { font-size:11px; font-weight:700; text-transform:uppercase; }
  .neighbor-file  { font-size:10px; color:var(--muted); margin-top:1px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .compact-audio { height:32px; width:220px; outline:none; border-radius:4px; accent-color:var(--accent); flex-shrink:0; margin-right:12px; }
  .compact-audio::-webkit-media-controls-enclosure { border-radius:4px; background:var(--surface2); }
  .compact-audio::-webkit-media-controls-play-button { filter: invert(1); }
  .compact-audio::-webkit-media-controls-mute-button { filter: invert(1); }
  .compact-audio::-webkit-media-controls-current-time-display,
  .compact-audio::-webkit-media-controls-time-remaining-display { color: var(--text); font-family: var(--mono); }

  /* Image neighbor row: scrollable grid */
  .img-grid-wrap { max-height:520px; overflow-y:auto; border-top:1px solid var(--border); background:var(--bg); }
  .img-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; padding:12px 14px; }
  .img-card { display:flex; flex-direction:column; gap:4px; cursor:pointer;
    transition:transform .15s; }
  .img-card:hover { transform:scale(1.03); }
  .img-thumb { width:100%; aspect-ratio:1/1; object-fit:cover; border-radius:5px;
    border:1px solid var(--border2); display:block; background:var(--surface2); }
  .img-rank { font-family:var(--display); font-size:13px; color:var(--muted); }
  .img-label { font-size:9px; text-transform:uppercase; letter-spacing:1px;
    overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }

  /* Dim selector buttons */
  .dim-btn { padding:4px 12px; border-radius:6px; border:1px solid var(--border2);
    background:var(--surface); color:var(--muted); cursor:pointer; font-size:11px;
    font-family:var(--mono); transition:all .15s; }
  .dim-btn:hover { color:var(--text); border-color:var(--accent); }
  .dim-btn.kd { background:rgba(0,229,160,.08); border-color:var(--accent); color:var(--accent); }
  .dim-btn.rt { background:rgba(255,140,66,.08); border-color:var(--orange); color:var(--orange); }

  .log-box { background:#040506; border:1px solid var(--border); border-radius:6px;
    padding:10px 12px; font-size:10px; color:var(--muted); max-height:88px; overflow-y:auto; line-height:1.9; flex-shrink:0; }
  .log-line { display:block; }
  .log-line.ok   { color:var(--accent); }
  .log-line.err  { color:var(--red); }
  .log-line.info { color:var(--blue); }
  .log-line.warn { color:var(--orange); }

  .idle-hint { display:flex; flex-direction:column; align-items:center; justify-content:center;
    flex:1; gap:10px; color:var(--muted); font-size:12px; text-align:center; padding:40px; }
  .idle-hint .big { font-size:34px; margin-bottom:6px; }

  .waveform { display:flex; align-items:flex-end; gap:3px; height:22px; flex-shrink:0; }
  .wave-bar { width:3px; background:var(--accent); border-radius:2px 2px 0 0; opacity:.8; animation:wave 1s ease-in-out infinite; }
  @keyframes wave{0%,100%{transform:scaleY(.3)}50%{transform:scaleY(1)}}

  ::-webkit-scrollbar { width:4px; height:4px; }
  ::-webkit-scrollbar-track { background:transparent; }
  ::-webkit-scrollbar-thumb { background:var(--border2); border-radius:2px; }
`;
document.head.appendChild(style);

const ALL_DIMS = [2, 5, 10, 20, 30];
const DIM_META = {
  2:  {color:'var(--accent)', label:'2D'},
  5:  {color:'var(--blue)',   label:'5D'},
  10: {color:'var(--yellow)', label:'10D'},
  20: {color:'var(--purple)', label:'20D'},
  30: {color:'#00d4d4',       label:'30D'},
};
const GENRE_COLORS = {
  blues:'#3d9bff', classical:'#b06cff', country:'#ffb830', disco:'#00e5a0',
  hiphop:'#ff3d6b', jazz:'#00d4d4', metal:'#ff6b3d', pop:'#e5a000',
  reggae:'#3dff6b', rock:'#ff3db0',
};
const gc = g => GENRE_COLORS[g?.toLowerCase()] || 'var(--accent)';

function WaveformAnim() {
  return (
    <div className="waveform">
      {Array.from({length:10},(_,i)=>(
        <div key={i} className="wave-bar"
          style={{height:`${20+Math.random()*80}%`,animationDelay:`${i*.06}s`,
                  animationDuration:`${.6+Math.random()*.8}s`}}/>
      ))}
    </div>
  );
}

function RaceBar({label,time,maxTime,color}) {
  const pct = maxTime>0?(time/maxTime)*100:0;
  return (
    <div className="race-row">
      <div className="race-row-header">
        <span className="race-name">{label}</span>
        <span className="race-time" style={{color}}>
          {time?.toLocaleString()} <span style={{fontSize:11,fontWeight:400}}>µs</span>
        </span>
      </div>
      <div className="race-bar-bg"><div className="race-bar" style={{width:`${pct}%`,background:color}}/></div>
    </div>
  );
}

// ── Audio neighbor list ───────────────────────────────────────────────────────
function AudioNeighborList({neighbors, treeLabel, treeColor, dimLabel, timeUs, linUs, speedup}) {
  if (!neighbors?.length) return (
    <div style={{padding:'12px 16px',color:'var(--muted)',fontSize:12}}>No audio neighbors found.</div>
  );

  return (
    <div className="neighbor-block" style={{borderColor:treeColor}}>
      <div className="neighbor-block-hdr">
        <span style={{color:treeColor, fontWeight:700}}>{treeLabel} · {dimLabel} Space · {neighbors.length} results</span>
        <span>
          <span style={{color:treeColor,fontWeight:700}}>{timeUs?.toLocaleString()} µs</span>
          <span style={{color:'var(--muted)',margin:'0 8px'}}>vs</span>
          <span style={{color:'var(--red)'}}>{linUs?.toLocaleString()} µs</span>
          <span style={{marginLeft:10,color:treeColor,fontWeight:700, fontSize:14}}>{speedup}×</span>
        </span>
      </div>
      {neighbors.map((n, i) => {
        const label = n.genre || 'unknown';
        const fname = n.filename || n.real_file || '—';
        const color = gc(n.genre);
        const audioSrc = n.url ? `${API}${n.url}` : null;

        return (
          <React.Fragment key={`audio-${n.record_id}-${i}`}>
            <div className="neighbor-row-audio">
              <div className="neighbor-rank" style={{color:treeColor}}>{i+1}</div>
              
              <div className="neighbor-info">
                <div className="neighbor-label" style={{color}}>{label}</div>
                <div className="neighbor-file">{fname}</div>
              </div>
              
              {/* COMPACT AUDIO PLAYER MOVED HERE */}
              {audioSrc ? (
                <audio controls controlsList="nodownload" preload="none" className="compact-audio">
                  <source src={audioSrc} type="audio/wav"/>
                  <source src={audioSrc} type="audio/mpeg"/>
                  Your browser does not support the audio element.
                </audio>
              ) : (
                <span style={{fontSize:11,color:'var(--red)', marginRight:12}}>⚠ Missing audio file</span>
              )}

              <div style={{fontSize:10,color:'var(--muted)',textAlign:'right',flexShrink:0, minWidth:'45px'}}>
                <div>ID #{n.record_id}</div>
              </div>
            </div>
          </React.Fragment>
        );
      })}
    </div>
  );
}

// ── Image neighbor grid ───────────────────────────────────────────────────────
function ImageNeighborList({neighbors, treeLabel, treeColor, dimLabel, timeUs, linUs, speedup}) {
  if (!neighbors?.length) return (
    <div style={{padding:'8px 14px',color:'var(--muted)',fontSize:11}}>No neighbors found.</div>
  );

  return (
    <div className="neighbor-block" style={{borderColor:treeColor}}>
      <div className="neighbor-block-hdr">
        <span style={{color:treeColor}}>{treeLabel} · {dimLabel} · {neighbors.length} results</span>
        <span>
          <span style={{color:treeColor,fontWeight:700}}>{timeUs?.toLocaleString()} µs</span>
          <span style={{color:'var(--muted)',margin:'0 5px'}}>vs</span>
          <span style={{color:'var(--red)'}}>{linUs?.toLocaleString()} µs</span>
          <span style={{marginLeft:8,color:treeColor,fontWeight:700}}>{speedup}×</span>
        </span>
      </div>
      {/* Show images in a scrollable 3-column grid */}
      <div className="img-grid-wrap">
        <div className="img-grid">
          {neighbors.map((n, i) => {
            const imgSrc = n.url ? `${API}${n.url}` : null;
            const label  = n.label || 'unknown';
            return (
              <div key={i} className="img-card"
                onClick={() => imgSrc && window.open(imgSrc, '_blank')}>
                {imgSrc ? (
                  <img
                    src={imgSrc}
                    alt={label}
                    className="img-thumb"
                    loading="lazy"
                    onError={e => {
                      e.target.style.display = 'none';
                      e.target.nextSibling && (e.target.nextSibling.style.display = 'flex');
                    }}
                  />
                ) : null}
                {/* Fallback placeholder shown if image fails or no URL */}
                <div style={{
                  display: imgSrc ? 'none' : 'flex',
                  width:'100%', aspectRatio:'1/1', borderRadius:5,
                  border:'1px solid var(--border2)', alignItems:'center',
                  justifyContent:'center', background:'var(--surface2)',
                  fontSize:20
                }}>🐕</div>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                  <span className="img-rank" style={{color:treeColor}}>#{i+1}</span>
                  <span style={{fontSize:9,color:'var(--muted)'}}>ID {n.record_id}</span>
                </div>
                <div className="img-label" style={{color:'var(--yellow)'}}>{label}</div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ── Reusable results panel ────────────────────────────────────────────────────
function ResultsPanel({kdResults, rtResults, loading, mediaType, loadingMsg}) {
  const [userKdDim, setUserKdDim] = useState(null);
  const [userRtDim, setUserRtDim] = useState(null);

  const firstKd = kdResults
    ? ALL_DIMS.find(d => kdResults[d] && !kdResults[d].error && kdResults[d].neighbors?.length)
    : null;
  const firstRt = rtResults
    ? ALL_DIMS.find(d => rtResults[d] && !rtResults[d].error && rtResults[d].neighbors?.length)
    : null;

  const activeKdDim = (userKdDim != null && kdResults?.[userKdDim]?.neighbors?.length)
    ? userKdDim : firstKd;
  const activeRtDim = (userRtDim != null && rtResults?.[userRtDim]?.neighbors?.length)
    ? userRtDim : firstRt;

  const setKdDim = d => setUserKdDim(prev => prev === d ? null : d);
  const setRtDim = d => setUserRtDim(prev => prev === d ? null : d);

  const isAudio = mediaType === 'audio';

  if (loading) return (
    <div className="card">
      <div className="card-title">Searching…</div>
      <div className="loading-bar"/>
      <div style={{marginTop:10,fontSize:11,color:'var(--muted)'}}>{loadingMsg}</div>
    </div>
  );

  if (!kdResults && !rtResults) return (
    <div className="idle-hint">
      <span className="big">{isAudio ? '🎵' : '🐶'}</span>
      <strong>Results appear here</strong>
      <span>Upload {isAudio ? 'an audio file' : 'a dog image'} on the left</span>
    </div>
  );

  return (
    <>
      {/* Performance table */}
      <div className="section-head">Performance — {mediaType==='audio'?'99K':'12K'} Records</div>
      <div className="card" style={{padding:'10px 0'}}>
        <table>
          <thead>
            <tr>
              {['Dim','KD-Tree','R-Tree','Linear','KD ×','RT ×','Winner'].map(h=>(
                <th key={h} style={{paddingLeft:12}}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ALL_DIMS.map(d => {
              const kd = kdResults?.[d]; const rt = rtResults?.[d];
              const col = DIM_META[d]?.color;
              const kdT = kd && !kd.error ? kd.kdtree_time_us : null;
              // RT is only valid if it returned neighbors — empty result (0 neighbors) means index not built properly
              const rtValid = rt && !rt.error && rt.neighbors?.length > 0;
              const rtT = rtValid ? rt.rtree_time_us : null;
              const linT = kd?.linear_time_us ?? rt?.linear_time_us;
              const kdSp = kd?.speedup; const rtSp = rtValid ? rt.speedup : null;
              // Color speedup: green if >= 2, yellow if 1-2, red if < 1
              const spColor = sp => sp == null ? 'var(--muted)' : sp >= 2 ? 'var(--accent)' : sp >= 1 ? 'var(--yellow)' : 'var(--red)';
              // Determine winner among valid trees
              const times = [kdT, rtT, linT].filter(Boolean);
              const minT  = times.length ? Math.min(...times) : null;
              const winner = minT == null ? '—'
                : minT === kdT ? <span style={{color:'var(--accent)'}}>KD-Tree</span>
                : minT === rtT ? <span style={{color:'var(--orange)'}}>R-Tree</span>
                : <span style={{color:'var(--red)'}}>Linear</span>;
              return (
                <tr key={d}>
                  <td style={{color:col,fontWeight:700,paddingLeft:12}}>{d}D</td>
                  <td style={{paddingLeft:12}}>
                    {kdT
                      ? <span style={{color: minT===kdT ? 'var(--accent)' : 'var(--muted)', fontWeight: minT===kdT?700:400}}>{kdT.toLocaleString()} µs</span>
                      : <span style={{color:'var(--muted)',fontSize:10}}>{kd?.error||'—'}</span>}
                  </td>
                  <td style={{paddingLeft:12}}>
                    {rtT
                      ? <span style={{color: minT===rtT ? 'var(--orange)' : 'var(--muted)', fontWeight: minT===rtT?700:400}}>{rtT.toLocaleString()} µs</span>
                      : <span style={{color:'var(--muted)',fontSize:10}}>{d===30?'skipped (segfault)':rt?.error||'—'}</span>}
                  </td>
                  <td style={{paddingLeft:12}}>
                    {linT
                      ? <span style={{color: minT===linT ? 'var(--red)' : 'var(--muted)', fontWeight: minT===linT?700:400}}>{linT.toLocaleString()} µs</span>
                      : '—'}
                  </td>
                  <td style={{color:spColor(kdSp),fontWeight:700,paddingLeft:12}}>{kdSp != null ? `${kdSp}×` : '—'}</td>
                  <td style={{color:spColor(rtSp),fontWeight:700,paddingLeft:12}}>{rtSp != null ? `${rtSp}×` : '—'}</td>
                  <td style={{paddingLeft:12}}>{winner}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* KD-Tree neighbors */}
      <div className="section-head">🌲 KD-Tree Nearest Neighbors</div>
      <div style={{display:'flex',gap:6,flexWrap:'wrap',flexShrink:0}}>
        {ALL_DIMS.map(d => {
          const r = kdResults?.[d]; const ok = r && !r.error && r.neighbors?.length;
          const col = DIM_META[d]?.color;
          return (
            <button key={d} className={`dim-btn ${activeKdDim===d?'kd':''}`}
              onClick={() => ok && setKdDim(d)}
              style={{
                opacity: ok?1:0.35, cursor: ok?'pointer':'not-allowed',
                borderColor: activeKdDim===d ? col : undefined,
                color: activeKdDim===d ? col : undefined
              }}>
              {d}D {ok ? `${r.speedup}×` : '—'}
            </button>
          );
        })}
      </div>

      {activeKdDim != null && kdResults?.[activeKdDim] && !kdResults[activeKdDim].error && (
        isAudio ? (
          <AudioNeighborList
            neighbors={kdResults[activeKdDim].neighbors}
            treeLabel="KD-Tree" treeColor="var(--accent)"
            dimLabel={`${activeKdDim}D`}
            timeUs={kdResults[activeKdDim].kdtree_time_us}
            linUs={kdResults[activeKdDim].linear_time_us}
            speedup={kdResults[activeKdDim].speedup}
          />
        ) : (
          <ImageNeighborList
            neighbors={kdResults[activeKdDim].neighbors}
            treeLabel="KD-Tree" treeColor="var(--accent)"
            dimLabel={`${activeKdDim}D`}
            timeUs={kdResults[activeKdDim].kdtree_time_us}
            linUs={kdResults[activeKdDim].linear_time_us}
            speedup={kdResults[activeKdDim].speedup}
          />
        )
      )}

      {/* R-Tree neighbors */}
      <div className="section-head">📦 R-Tree Nearest Neighbors</div>
      <div style={{display:'flex',gap:6,flexWrap:'wrap',flexShrink:0}}>
        {ALL_DIMS.map(d => {
          const r = rtResults?.[d]; const ok = r && !r.error && r.neighbors?.length;
          return (
            <button key={d} className={`dim-btn ${activeRtDim===d?'rt':''}`}
              onClick={() => ok && setRtDim(d)}
              style={{
                opacity: ok?1:0.35, cursor: ok?'pointer':'not-allowed',
                borderColor: activeRtDim===d ? 'var(--orange)' : undefined,
                color: activeRtDim===d ? 'var(--orange)' : undefined
              }}>
              {d}D {ok ? `${r.speedup}×` : (r?.error ? '✗' : '—')}
            </button>
          );
        })}
      </div>

      {activeRtDim != null && rtResults?.[activeRtDim] && !rtResults[activeRtDim].error && (
        isAudio ? (
          <AudioNeighborList
            neighbors={rtResults[activeRtDim].neighbors}
            treeLabel="R-Tree" treeColor="var(--orange)"
            dimLabel={`${activeRtDim}D`}
            timeUs={rtResults[activeRtDim].rtree_time_us}
            linUs={rtResults[activeRtDim].linear_time_us}
            speedup={rtResults[activeRtDim].speedup}
          />
        ) : (
          <ImageNeighborList
            neighbors={rtResults[activeRtDim].neighbors}
            treeLabel="R-Tree" treeColor="var(--orange)"
            dimLabel={`${activeRtDim}D`}
            timeUs={rtResults[activeRtDim].rtree_time_us}
            linUs={rtResults[activeRtDim].linear_time_us}
            speedup={rtResults[activeRtDim].speedup}
          />
        )
      )}

      {!ALL_DIMS.some(d => rtResults?.[d] && !rtResults[d].error) && (
        <div style={{fontSize:11,color:'var(--muted)'}}>
          ⚠ R-Tree indexes not found — run <code style={{color:'var(--accent)'}}>python scripts/preprocess.py</code>
        </div>
      )}
    </>
  );
}

// ── Shared upload left panel ───────────────────────────────────────────────────
function UploadPanel({mediaType, kValue, setKValue, onFile, loading, fileName, inputSrc, logs}) {
  const [dragOver, setDragOver] = useState(false);
  const isAudio = mediaType === 'audio';
  const icon  = loading ? '⚙️' : fileName ? (isAudio ? '🎵' : '🐶') : (isAudio ? '🎧' : '🐕');
  const title = loading ? 'Searching…' : fileName || `Drop ${isAudio ? 'Audio' : 'Image'} Here`;
  const sub   = loading ? '' : fileName ? 'Drop another to re-search' : isAudio ? '.mp3 · .wav · .ogg' : '.jpg · .jpeg · .png';
  const accept = isAudio ? '.mp3,.wav,.ogg,.flac' : '.jpg,.jpeg,.png,.webp';

  return (
    <div className="panel-left">
      <div className="section-head">{isAudio ? 'Audio' : 'Image'} Similarity Search</div>

      <div className={`upload-zone ${dragOver ? 'drag-over' : ''}`}
        onDragOver={e => {e.preventDefault(); setDragOver(true);}}
        onDragLeave={() => setDragOver(false)}
        onDrop={e => {e.preventDefault(); setDragOver(false); onFile(e.dataTransfer.files[0]);}}>
        <input type="file" accept={accept} onChange={e => onFile(e.target.files[0])}/>
        <span className="upload-icon">{icon}</span>
        <div className="upload-title" style={{fontSize: fileName ? 14 : 17}}>{title}</div>
        <div className="upload-sub">{sub}</div>
        {loading && <div style={{marginTop:10,width:'100%'}}><div className="loading-bar"/></div>}
        {loading && <div style={{marginTop:10}}><WaveformAnim/></div>}
      </div>

      {/* Preview uploaded file */}
      {inputSrc && !loading && (
        <div style={{flexShrink:0}}>
          <div style={{fontSize:9,color:'var(--muted)',letterSpacing:'2px',textTransform:'uppercase',marginBottom:4}}>
            Your Upload
          </div>
          {isAudio ? (
            <audio src={inputSrc} controls
              style={{width:'100%',height:28,borderRadius:3,outline:'none',display:'block',accentColor:'var(--accent)'}}/>
          ) : (
            <img src={inputSrc} alt="query"
              style={{width:'100%',maxHeight:180,objectFit:'contain',
                borderRadius:6,border:'1px solid var(--border2)',background:'#060708'}}/>
          )}
        </div>
      )}

      <div className="slider-row" style={{flexShrink:0}}>
        <span className="slider-label">K = {kValue}</span>
        <input type="range" min="1" max="10" value={kValue}
          onChange={e => setKValue(parseInt(e.target.value))}/>
        <span style={{fontSize:11,color:'var(--muted)'}}>neighbors</span>
      </div>

      <div className="log-box">
        {logs.map((l,i) => <span key={i} className={`log-line ${l.type}`}>{l.msg}</span>)}
      </div>
    </div>
  );
}

// ── Audio Tab ─────────────────────────────────────────────────────────────────
function TabAudio({onResult, kdResults, rtResults, loading}) {
  const [fileName, setFileName] = useState(null);
  const [inputSrc, setInputSrc] = useState(null);
  const [kValue,   setKValue]   = useState(5);
  const [logs, setLogs] = useState([
    {msg:'// Drop .mp3 or .wav to search', type:''},
    {msg:'// KD-Tree + R-Tree at 2D/5D/10D/20D/30D · 99K records', type:'info'},
  ]);
  useEffect(() => () => {if (inputSrc) URL.revokeObjectURL(inputSrc);}, [inputSrc]);
  const addLog = (m, t='') => setLogs(l => [...l.slice(-12), {msg:m, type:t}]);

  const handleFile = async (file) => {
    if (!file) return;
    setFileName(file.name);
    if (inputSrc) URL.revokeObjectURL(inputSrc);
    setInputSrc(URL.createObjectURL(file));
    addLog(`// ${file.name}  (${(file.size/1024).toFixed(1)} KB)`, 'info');
    addLog('// PCA projection → KD-Tree + R-Tree …');
    onResult(null, null, true);
    const fd = new FormData(); fd.append('file', file);
    try {
      const res = await fetch(`${API}/api/search_audio?k=${kValue}`, {method:'POST', body:fd});
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      const data = await res.json();
      const kd = {}, rt = {};
      Object.keys(data.kd_results || {}).forEach(k => {kd[parseInt(k)] = data.kd_results[k];});
      Object.keys(data.rt_results || {}).forEach(k => {rt[parseInt(k)] = data.rt_results[k];});
      ALL_DIMS.forEach(d => {
        const k = kd[d], r = rt[d];
        if (k && !k.error) addLog(`// KD ${d}D: ${k.kdtree_time_us}µs  ${k.speedup}×  (${k.neighbors?.length||0} neighbors)`, k.speedup>=2?'ok':k.speedup>=1?'info':'err');
        if (r && !r.error) addLog(`// RT ${d}D: ${r.rtree_time_us}µs  ${r.speedup}×`, r.speedup>=2?'ok':r.speedup>=1?'info':'warn');
      });
      onResult(kd, rt, false);
    } catch(err) {
      addLog(`// Error: ${err.message}`, 'err');
      onResult(null, null, false);
    }
  };

  return (
    <>
      <UploadPanel mediaType="audio" kValue={kValue} setKValue={setKValue}
        onFile={handleFile} loading={loading} fileName={fileName} inputSrc={inputSrc} logs={logs}/>
      <div className="panel-right">
        <ResultsPanel kdResults={kdResults} rtResults={rtResults} loading={loading}
          mediaType="audio" loadingMsg="PCA → 5 KD-Tree + 5 R-Tree indexes · 99K records each"/>
      </div>
    </>
  );
}

// ── Image Tab ─────────────────────────────────────────────────────────────────
function TabImage({onResult, kdResults, rtResults, loading}) {
  const [fileName, setFileName] = useState(null);
  const [inputSrc, setInputSrc] = useState(null);
  const [kValue,   setKValue]   = useState(5);
  const [logs, setLogs] = useState([
    {msg:'// Drop a dog image to search', type:''},
    {msg:'// MobileNetV2 CNN → PCA → KD-Tree + R-Tree', type:'info'},
    {msg:'// Dataset: Stanford Dogs (Kaggle)', type:''},
  ]);
  useEffect(() => () => {if (inputSrc) URL.revokeObjectURL(inputSrc);}, [inputSrc]);
  const addLog = (m, t='') => setLogs(l => [...l.slice(-12), {msg:m, type:t}]);

  const handleFile = async (file) => {
    if (!file) return;
    setFileName(file.name);
    if (inputSrc) URL.revokeObjectURL(inputSrc);
    setInputSrc(URL.createObjectURL(file));
    addLog(`// ${file.name}  (${(file.size/1024).toFixed(1)} KB)`, 'info');
    addLog('// Extracting CNN features → PCA → searching …');
    onResult(null, null, true);
    const fd = new FormData(); fd.append('file', file);
    try {
      const res = await fetch(`${API}/api/search_image?k=${kValue}`, {method:'POST', body:fd});
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      const data = await res.json();
      const kd = {}, rt = {};
      Object.keys(data.kd_results || {}).forEach(k => {kd[parseInt(k)] = data.kd_results[k];});
      Object.keys(data.rt_results || {}).forEach(k => {rt[parseInt(k)] = data.rt_results[k];});
      ALL_DIMS.forEach(d => {
        const k = kd[d], r = rt[d];
        if (k && !k.error) addLog(`// KD ${d}D: ${k.kdtree_time_us}µs  ${k.speedup}×  (${k.neighbors?.length||0} images)`, k.speedup>=2?'ok':k.speedup>=1?'info':'err');
        if (r && !r.error) addLog(`// RT ${d}D: ${r.rtree_time_us}µs  ${r.speedup}×`, r.speedup>=2?'ok':r.speedup>=1?'info':'warn');
      });
      onResult(kd, rt, false);
    } catch(err) {
      addLog(`// Error: ${err.message}`, 'err');
      onResult(null, null, false);
    }
  };

  return (
    <>
      <UploadPanel mediaType="image" kValue={kValue} setKValue={setKValue}
        onFile={handleFile} loading={loading} fileName={fileName} inputSrc={inputSrc} logs={logs}/>
      <div className="panel-right">
        <ResultsPanel kdResults={kdResults} rtResults={rtResults} loading={loading}
          mediaType="image" loadingMsg="CNN features → PCA → KD-Tree + R-Tree search …"/>
      </div>
    </>
  );
}

// ── 2D Canvas Tab ─────────────────────────────────────────────────────────────
function Tab2D({onResult, metrics, loading}) {
  const canvasRef = useRef(null);
  const [kValue, setKValue] = useState(10);
  const [clicked, setClicked] = useState(false);
  const CANVAS = 440; const SCALE = CANVAS/1000;

  const drawGrid = useCallback(ctx => {
    ctx.fillStyle = '#060708'; ctx.fillRect(0,0,CANVAS,CANVAS);
    ctx.strokeStyle = '#0c0e12'; ctx.lineWidth = 1;
    for (let x=0; x<=CANVAS; x+=44) {ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,CANVAS);ctx.stroke();}
    for (let y=0; y<=CANVAS; y+=44) {ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(CANVAS,y);ctx.stroke();}
  }, []);

  useEffect(() => {drawGrid(canvasRef.current.getContext('2d'));}, [drawGrid]);

  const handleClick = async e => {
    if (loading) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const px = e.clientX-rect.left, py = e.clientY-rect.top;
    onResult(null, true);
    try {
      const res = await fetch(`${API}/api/search`, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({x:px/SCALE, y:py/SCALE, k:kValue})
      });
      const data = await res.json(); onResult(data, false); setClicked(true);
      const ctx = canvasRef.current.getContext('2d'); drawGrid(ctx);
      data.coordinates?.forEach(c => {
        ctx.strokeStyle='rgba(0,229,160,.12)'; ctx.lineWidth=1;
        ctx.beginPath(); ctx.moveTo(px,py); ctx.lineTo(c[0]*SCALE,c[1]*SCALE); ctx.stroke();
      });
      data.coordinates?.forEach((c,i) => {
        const a = 1-(i/data.coordinates.length)*0.45;
        ctx.beginPath(); ctx.arc(c[0]*SCALE,c[1]*SCALE,5,0,Math.PI*2);
        ctx.fillStyle = `rgba(0,229,160,${a})`; ctx.fill();
      });
      ctx.beginPath(); ctx.arc(px,py,7,0,Math.PI*2); ctx.fillStyle='var(--red)'; ctx.fill();
      ctx.strokeStyle='rgba(255,61,107,.4)'; ctx.lineWidth=1; ctx.setLineDash([4,4]);
      ctx.beginPath(); ctx.moveTo(px,0); ctx.lineTo(px,CANVAS); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(0,py); ctx.lineTo(CANVAS,py); ctx.stroke();
      ctx.setLineDash([]);
    } catch {onResult(null, false);}
  };

  const kd = metrics;
  const maxT = kd ? Math.max(kd.kdtree_time_us, kd.linear_time_us) : 0;

  return (
    <>
      <div className="panel-2d-left">
        <div className="section-head">2D KD-Tree — 100,000 random points</div>
        <div className="canvas-wrap">
          <canvas ref={canvasRef} width={CANVAS} height={CANVAS} onClick={handleClick}/>
          {!clicked && <div className="canvas-overlay"><span className="canvas-hint">Click to search nearest neighbours</span></div>}
        </div>
        <div className="slider-row">
          <span className="slider-label">K = {kValue}</span>
          <input type="range" min="1" max="50" value={kValue} onChange={e=>setKValue(parseInt(e.target.value))}/>
          <span style={{fontSize:11,color:'var(--muted)'}}>neighbours</span>
        </div>
      </div>
      <div className="panel-2d-right">
        <div className="section-head">Results</div>
        {loading && <div className="card"><div className="card-title">Searching…</div><div className="loading-bar"/></div>}
        {!loading && !kd && <div className="idle-hint"><span className="big">⬡</span><strong>Click on the canvas</strong></div>}
        {!loading && kd && (
          <>
            <div className="card">
              <div className="card-title" style={{color:'var(--accent)'}}>🌲 KD-Tree vs Linear</div>
              <RaceBar label="KD-Tree (Index)" time={kd.kdtree_time_us} maxTime={maxT} color="var(--accent)"/>
              <RaceBar label="Linear Scan"     time={kd.linear_time_us} maxTime={maxT} color="var(--red)"/>
            </div>
            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:8}}>
              <div className="card" style={{padding:'10px 12px'}}>
                <div className="card-title">Speedup</div>
                <div style={{fontFamily:'var(--display)',fontSize:36,color:'var(--accent)',lineHeight:1}}>{kd.speedup}×</div>
              </div>
              <div className="card" style={{padding:'10px 12px'}}>
                <div className="card-title">KD-Tree</div>
                <div style={{fontSize:13,fontWeight:700,color:'var(--accent)'}}>{kd.kdtree_time_us?.toLocaleString()} µs</div>
              </div>
              <div className="card" style={{padding:'10px 12px'}}>
                <div className="card-title">Linear</div>
                <div style={{fontSize:13,fontWeight:700,color:'var(--red)'}}>{kd.linear_time_us?.toLocaleString()} µs</div>
              </div>
            </div>
          </>
        )}
      </div>
    </>
  );
}

// ── About Tab ─────────────────────────────────────────────────────────────────
function TabAbout() {
  return (
    <div className="panel-about">
      <div style={{maxWidth:740}}>
        <div className="section-head" style={{marginBottom:14}}>Methods</div>
        {[
          {name:'Linear Scan',color:'var(--red)',cplx:'O(N·D)',what:'Reads every record, computes Euclidean distance, maintains max-heap of k best. Always correct.',when:'Baseline. Wins at high D or very small N.'},
          {name:'KD-Tree (Disk+LRU)',color:'var(--accent)',cplx:'O(log N)→O(N)',what:'Partitions space by cycling axes. Branch-and-bound pruning skips entire subtrees.',when:'Massive speedup at 2D–10D. Degrades past 20D.'},
          {name:'R-Tree (Disk+BPM)',color:'var(--orange)',cplx:'O(log N)→O(N)',what:'Groups points into Minimum Bounding Rectangles hierarchically. Prunes subtrees by MINDIST.',when:'Strong at 2D–15D. MBR overlap degrades at 20D+.'},
        ].map(m => (
          <div key={m.name} className="card" style={{marginBottom:10}}>
            <div style={{display:'flex',justifyContent:'space-between',marginBottom:8}}>
              <span style={{fontFamily:'var(--display)',fontSize:20,color:m.color}}>{m.name}</span>
              <span style={{fontSize:10,color:'var(--muted)'}}>{m.cplx}</span>
            </div>
            <p style={{fontSize:12,lineHeight:1.9,marginBottom:4}}>{m.what}</p>
            <p style={{fontSize:11,color:'var(--muted)',lineHeight:1.7}}>⚡ {m.when}</p>
          </div>
        ))}
        <div className="section-head" style={{margin:'20px 0 12px'}}>Why KD-Tree and R-Tree give different results</div>
        <div className="card">
          <p style={{fontSize:12,lineHeight:1.9,color:'var(--muted)'}}>
            Both trees find exact k-nearest neighbors but they traverse the space differently.
            KD-Tree splits by axis cycling; R-Tree splits by MBR overlap. At the same dimensionality,
            tie-breaking (equal distances), floating-point evaluation order, and tree traversal order
            may yield a different ordering among equidistant points. At lower dimensions both agree;
            at higher D, the pruning strategies diverge more significantly.
          </p>
        </div>
        <div className="section-head" style={{margin:'20px 0 12px'}}>Preprocessing Pipeline</div>
        <div className="card">
          {[
            ['Audio','features_3_sec.csv → 30 raw features → standardise → PCA → [2,5,10,20,30]D'],
            ['Images','MobileNetV2 (ImageNet) → 1280D embeddings → standardise → PCA → [2,5,10,20,30]D'],
            ['Both','Same PCA meta saved → live query projected identically at search time'],
            ['Indexes','KD-Tree + R-Tree built from same PCA vectors → disk-resident + LRU-cached'],
          ].map(([n,d]) => (
            <div key={n} style={{display:'flex',gap:10,fontSize:11,padding:'6px 0',borderBottom:'1px solid var(--border)'}}>
              <span style={{color:'var(--accent)',fontWeight:700,minWidth:60,flexShrink:0}}>{n}</span>
              <span style={{color:'var(--muted)'}}>{d}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Root ──────────────────────────────────────────────────────────────────────
export default function App() {
  const [tab,       setTab]     = useState('audio');
  const [loading,   setLoading] = useState(false);
  const [metrics2d, setMetrics] = useState(null);
  const [audioKD,   setAudioKD] = useState(null);
  const [audioRT,   setAudioRT] = useState(null);
  const [imageKD,   setImageKD] = useState(null);
  const [imageRT,   setImageRT] = useState(null);

  const on2D = useCallback((data, isLoading) => {
    setLoading(isLoading); if (data) setMetrics(data);
  }, []);

  const onAudio = useCallback((kd, rt, isLoading) => {
    setLoading(isLoading);
    if (kd !== null) setAudioKD(kd);
    if (rt !== null) setAudioRT(rt);
  }, []);

  const onImage = useCallback((kd, rt, isLoading) => {
    setLoading(isLoading);
    if (kd !== null) setImageKD(kd);
    if (rt !== null) setImageRT(rt);
  }, []);

  const TABS = [
    {id:'audio', label:'01 · Audio Search'},
    {id:'image', label:'02 · Image Search'},
    {id:'2d',    label:'03 · 2D Canvas'},
    {id:'about', label:'04 · How It Works'},
  ];

  return (
    <div id="root">
      <div className="header">
        <div className="header-dot"/>
        <div className="header-title">SQLMATES — KD-TREE + R-TREE BENCHMARK</div>
        <div className="header-sub">IIT Kharagpur · DBMS Project</div>
      </div>
      <div className="tabs">
        {TABS.map(t => (
          <button key={t.id} className={`tab ${tab===t.id?'active':''}`} onClick={() => setTab(t.id)}>{t.label}</button>
        ))}
      </div>
      <div className="page-body">
        {tab==='audio' && <TabAudio onResult={onAudio} kdResults={audioKD} rtResults={audioRT} loading={loading}/>}
        {tab==='image' && <TabImage onResult={onImage} kdResults={imageKD} rtResults={imageRT} loading={loading}/>}
        {tab==='2d'    && <Tab2D   onResult={on2D}    metrics={metrics2d}                     loading={loading}/>}
        {tab==='about' && <TabAbout/>}
      </div>
    </div>
  );
}