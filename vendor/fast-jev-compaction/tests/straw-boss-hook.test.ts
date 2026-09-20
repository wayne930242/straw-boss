import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { collectToolCalls } from '../src/state.js';
import { register } from '../../../hooks/jev-pruning.js';

const policy = JSON.parse(readFileSync(new URL('../../../config/jev-policy.json', import.meta.url), 'utf8'));
const criteria = JSON.parse(readFileSync(new URL('../../../config/jev-criteria.json', import.meta.url), 'utf8'));

function fixture() {
  return [
    { role: 'user', text: 'Keep this exact user text.', toolUses: [], handle: 'first' },
    { role: 'assistant', text: ' ', toolUses: [{tool_use_id:'a', tool:'Read', input:{file_path:'old.log'}}] },
    { role: 'user', text: '', toolUses: [], toolResults: [{tool_use_id:'a', text:'x'.repeat(2000)}] },
    ...Array.from({length:6}, (_, i) => ({role:i%2?'assistant':'user', text:`locked-${i}`, toolUses:[],handle:`h${i}`})),
  ];
}

function engine(overrides: Record<string, unknown> = {}) {
  const events: Record<string, any> = {};
  const writes: any[] = [];
  const notices: string[] = [];
  const env: Record<string,string> = {STRAW_BOSS_JEV:'1',TYPESAFE_API_KEY:'key'};
  const $: any = {
    plugin:{root:'/repo'}, env:{get:async(k:string)=>env[k],set:async(k:string,v:string)=>{env[k]=v;}},
    session:{id:async()=> 'session', model:async()=> 'test-model', usage:async()=>({context:{tokens:1000,window:1000000}})},
    ui:{log:(s:string)=>notices.push(s)},
    process:{run:async(argv:string[], init:any)=>{
      const data=JSON.parse(init.stdin);
      if(argv[2]==='config')return {exitCode:0,stdout:JSON.stringify({criteria,policy,criteria_version:'sha256:test'})};
      if(argv[2]==='measure')return {exitCode:0,stdout:JSON.stringify({tokens_before:1000,tokens_after:500,reduction_pct:50,gate_reduction_pct:50})};
      writes.push(data);
      return {exitCode:0,stdout:'{}'};
    }},
    http:{fetch:async(_url:string, init:any)=>{
      const request=JSON.parse(init.body);
      return {status:200,ok:true,text:JSON.stringify({model:'jev-1.test',usage:{input_tokens:100},
        answers:Object.fromEntries(Object.keys(request.questions).map(k=>[k,{type:'noul',noul:0.1}]))})};
    }},...overrides,
  };
  register(((name:string,handler:any)=>{events[name]=handler;}) as any, {});
  return {$,events,writes,notices,env};
}

describe('Straw Boss compaction boundary',()=>{
  it.each(['cat task.json', 'f=CLAUDE; cat "$f.md"'])('documents unmatched indirect input %s', (command)=>{
    const messages=fixture();
    messages[1].toolUses[0].input.file_path=command;
    const calls=collectToolCalls(messages, policy.preserve_recent_messages, policy.protected_input_patterns);
    expect(calls[0].governingSource).toBeUndefined();
    expect(calls[0].pinned).toBe(false);
  });
  it('missing and empty keys delegate silently without recording',async()=>{
    for(const key of [undefined,'',' ']){
      const h=engine();h.env.TYPESAFE_API_KEY=key as any;
      let next=0;const event={trigger:'manual',messages:fixture()};
      await h.events['session.compact'](h.$,event,async(e:any)=>{expect(e).toBe(event);next++;return {messages:[]};});
      expect(next).toBe(1);expect(h.writes).toEqual([]);expect(h.notices).toEqual([]);
    }
  });
  it('applies only measured candidates, retaining text with fresh engine identities',async()=>{
    const h=engine();const messages=fixture();
    const result=await h.events['session.compact'](h.$,{trigger:'manual',messages},()=>{throw Error('unexpected fallback');});
    expect(result.messages[0].text).toBe(messages[0].text);
    expect(result.messages.every((m:any)=>m.handle===undefined)).toBe(true);
    expect(result.messages[1].text).toBe(' ');
    expect(result.messages.slice(-6).map((m:any)=>m.text)).toEqual(messages.slice(-6).map(m=>m.text));
    expect(h.writes).toHaveLength(1);
    expect(h.writes[0].record.decision).toBe('apply');
    expect(h.writes[0].record.outcome).toBe(null);
    expect(h.writes[0].record.application.status).toBe('awaiting-backend-usage');
    expect(h.writes[0].record.jev.input_tokens).toBe(100);
    expect(h.writes[0].record.jev.model).toBe('jev-1.test');
    expect(h.writes[0].original_messages).toEqual(messages);
  });
  it('measurement below the gate delegates original history',async()=>{
    const h=engine();const run=h.$.process.run;
    h.$.process.run=async(a:any,i:any)=>a[2]==='measure'?{exitCode:0,stdout:'{"gate_reduction_pct":9.9}'}:run(a,i);
    const event={trigger:'auto',messages:fixture()};let calls=0;
    await h.events['session.compact'](h.$,event,async(e:any)=>{expect(e).toBe(event);calls++;return {messages:[]};});
    expect(calls).toBe(1);expect(h.writes[0].record.fallback_reason).toBe('under-reduction-gate');
  });
  it('a failed recovery write delegates instead of applying a candidate',async()=>{
    const h=engine();const run=h.$.process.run;
    h.$.process.run=async(a:any,i:any)=>a[2]==='persist'?{exitCode:1,stdout:'{"error":"OSError"}'}:run(a,i);
    let calls=0;await h.events['session.compact'](h.$,{trigger:'manual',messages:fixture()},async()=>{calls++;return {messages:[]};});
    expect(calls).toBe(1);expect(h.notices[0]).toContain('recovery record unavailable');
  });
  it('Jev failure records one fallback with no server body',async()=>{
    const h=engine();h.$.http.fetch=async()=>({ok:false,status:500,text:'private server detail'});
    let calls=0;await h.events['session.compact'](h.$,{trigger:'manual',messages:fixture()},async()=>{calls++;return {messages:[]};});
    expect(calls).toBe(1);expect(h.writes).toHaveLength(1);
    expect(h.writes[0].record.fallback_reason).toBe('jev-http-500');
    expect(JSON.stringify(h.writes)).not.toContain('private server detail');
  });
  it.each(['/home/user/.straw-boss/dispatch/task.json', 'cd ~/.straw-boss/dispatch && cat task.json', 'cat CLAUDE.md', 'cat .claude/CLAUDE.md'])('keeps recognized governing input %s even when the judge would discard it',async(input)=>{
    const h=engine();const messages=fixture();
    messages[1].toolUses[0].input.file_path=input;
    let next=0;
    await h.events['session.compact'](h.$,{trigger:'manual',messages},async()=>{next++;return {messages:[]};});
    expect(next).toBe(1);
    expect(h.writes[0].record.decisions[0].reason).toBe('governing_source');
    expect(h.writes[0].record.decisions[0].action).toBe('keep');
    expect(h.writes[0].record.jev.requests).toBe(0);
  });
});
