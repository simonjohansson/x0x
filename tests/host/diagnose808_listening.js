// Exercise the real report controller without playback or human-listening claims.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync('tools/x0x/diagnose808.html', 'utf8');
const elements = new Map();
function element(id) {
  if (!elements.has(id)) elements.set(id, {hidden:false,disabled:false,textContent:'',value:0,append(){},click(){}});
  return elements.get(id);
}
let randomState=123456789, exported, starts=0, stops=0;
Object.assign(element('player'),{paused:true,currentTime:0,
  pause(){if(!this.paused)stops++;this.paused=true},
  async play(){if(this.failNext){this.failNext=false;throw Error('blocked')}starts++;this.paused=false}});
const data={gain:4,gain_applied:true,playback_encoding:'PCM_24',manifest:{source_sha256:'test',scope:'Complete host candidate; development cohort'},stimuli:Array.from({length:16},(_,i)=>({tone:i,decay:i,recorded:'AA==',candidate:'AA==',recorded_download:`${i}-recorded.wav`,candidate_download:`${i}-candidate.wav`}))};
const context=vm.createContext({document:{getElementById:element,querySelectorAll(){return []},createElement:element},
  crypto:{getRandomValues(array){randomState^=randomState<<13;randomState^=randomState>>>17;randomState^=randomState<<5;array[0]=randomState>>>0;return array}},
  atob,Blob:class {constructor(parts){if(typeof parts[0]==='string')exported=JSON.parse(parts[0])}},
  URL:{createObjectURL(){return 'blob:test'},revokeObjectURL(){}},setTimeout(fn){fn()}});
const script=html.match(/<script>([\s\S]*?)<\/script>/)[1].replace('__LISTENING_DATA__',JSON.stringify(data));
vm.runInContext(script,context);
assert.equal(vm.runInContext('binomialTail(12,16)',context),.0384063720703125);
assert.equal(vm.runInContext('binomialTail(16,16)',context),1/65536);
assert.equal(vm.runInContext('binomialTail(0,16)',context),1);
element('answer-a').onclick(); // A vote before starting is harmless.
element('start').onclick();
assert.equal(element('preview').hidden,true);
assert.equal(element('download').disabled,true);
assert.equal(vm.runInContext('new Set(session.trials.map(t=>t.index)).size',context),16);
assert.equal(vm.runInContext('session.trials.every(t=>t.a!==t.b)',context),true);
assert.equal(vm.runInContext('new Set(session.trials.map(t=>t.x)).size',context),2);
for(let i=0;i<16;i++){
  if(i<16){assert.equal(element('result').textContent,'');assert.equal(element('download').disabled,true)}
  const choice=vm.runInContext('session.trials[session.answers.length].x',context);
  element('answer-'+choice).onclick();
}
assert.equal(vm.runInContext('session.correct',context),16);
assert.equal(element('download').disabled,false);
element('download').onclick();
assert.equal(exported.manifest.source_sha256,'test');
assert.equal(exported.scope,data.manifest.scope);
assert.equal(exported.session.answers.length,16);
assert.equal(exported.settings.length,16);
assert.equal(JSON.stringify(exported).includes('AA=='),false);
element('start').onclick();
for(let i=0;i<16;i++){
  const wrong=vm.runInContext("session.trials[session.answers.length].x==='a'?'b':'a'",context);
  element('answer-'+wrong).onclick();
}
assert.equal(vm.runInContext('session.correct',context),0);
assert.match(element('result').textContent,/does not prove equivalence/);
Promise.all([element('recorded').onclick(),element('candidate').onclick()]).then(()=>{
  assert.equal(starts,2);assert.equal(stops,1);
  assert.equal(element('playing').textContent,'Playing candidate');
  assert.equal(element('recorded-download').href,'0-recorded.wav');
  element('player').failNext=true;
  return element('recorded').onclick();
}).then(()=>{
  assert.equal(stops,2);assert.match(element('playing').textContent,/Could not play.*blocked/);
  console.log('ABX/native-media controller checks passed; synthetic responses only.');
}).catch(error=>{console.error(error);process.exitCode=1});
