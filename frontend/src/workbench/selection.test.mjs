import test from 'node:test'
import assert from 'node:assert/strict'
import {triage,diversify,preparationFocus} from './selection.js'
const row={name:'样本',score:80,pct_chg:3,amount:2e8,volume_ratio:2,freshness:{state:'fresh'},industry:'电子'}
test('stale or incomplete candidates never enter focus',()=>{
 assert.equal(triage(row,'live','short').tier,'focus')
 assert.equal(triage({...row,freshness:{state:'stale'}},'live','short').tier,'pending')
 assert.equal(triage({...row,score:null},'live','short').tier,'pending')
 assert.equal(triage({...row,in_pool:true},'live','short').tier,'excluded')
})
test('caps do not refill from weaker tiers or concentrate one industry',()=>{
 const rows=Array.from({length:20},(_,i)=>({...row,code:String(i),industry:i<10?'电子':'医药'}))
 assert.equal(diversify(rows,5,2).length,4)
 assert.equal(preparationFocus(rows.map(r=>({...r,overlap:1,price:10}))).length,0)
 assert.equal(preparationFocus(rows.map(r=>({...r,overlap:2,price:10}))).length,4)
})
