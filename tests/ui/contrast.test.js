const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const css=fs.readFileSync(require('node:path').join(__dirname,'../../laew/ui/app.css'),'utf8');
const tokens=block=>Object.fromEntries([...block.matchAll(/--([\w-]+):\s*(#[\da-f]{6})\s*;/gi)].map(m=>[m[1],m[2]]));
const light=tokens(css.match(/:root\s*\{([^}]+)\}/)[1]);
const dark={...light,...tokens(css.match(/:root\[data-theme="dark"\]\s*\{([^}]+)\}/)[1])};
function luminance(hex){
  const rgb=[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16)/255).map(c=>c<=.04045?c/12.92:((c+.055)/1.055)**2.4);
  return rgb[0]*.2126+rgb[1]*.7152+rgb[2]*.0722;
}
for(const [name,palette] of Object.entries({light,dark}))test(`${name} text and semantic action colors meet WCAG AA contrast`,()=>{
  for(const [fg,bg] of [['text','bg'],['text-2','surface'],['muted','bg'],['faint','surface'],['accent','accent-wash'],['on-primary','primary'],['red','red-wash'],['amber','amber-wash'],['green','surface']]){
    const a=luminance(palette[fg]),b=luminance(palette[bg]),ratio=(Math.max(a,b)+.05)/(Math.min(a,b)+.05);
    assert.ok(ratio>=4.5,`${fg}/${bg}: ${ratio.toFixed(2)}`);
  }
});
