// Podgląd: zestawienie kilku PNG w siatkę na ciemnym tle. Użycie: node contact_sheet.mjs out.png a.png b.png ...
import fs from "node:fs"; import zlib from "node:zlib";
import { encodePNG } from "./dds.mjs";
function readPNG(p){const b=fs.readFileSync(p);let o=8,w,h,idat=[];while(o<b.length){const len=b.readUInt32BE(o),t=b.toString("ascii",o+4,o+8);if(t==="IHDR"){w=b.readUInt32BE(o+8);h=b.readUInt32BE(o+12);}if(t==="IDAT")idat.push(b.subarray(o+8,o+8+len));o+=12+len;}
const raw=zlib.inflateSync(Buffer.concat(idat)),bpp=4,st=w*bpp,out=new Uint8Array(w*h*4);let prev=new Uint8Array(st);
for(let y=0;y<h;y++){const f=raw[y*(st+1)],line=raw.subarray(y*(st+1)+1,(y+1)*(st+1)),cur=new Uint8Array(st);for(let i=0;i<st;i++){const a=i>=bpp?cur[i-bpp]:0,bb=prev[i],c=i>=bpp?prev[i-bpp]:0;let v=line[i];if(f===1)v+=a;else if(f===2)v+=bb;else if(f===3)v+=(a+bb)>>1;else if(f===4){const p=a+bb-c,pa=Math.abs(p-a),pb=Math.abs(p-bb),pc=Math.abs(p-c);v+=pa<=pb&&pa<=pc?a:pb<=pc?bb:c;}cur[i]=v&255;}out.set(cur,y*st);prev=cur;}return{w,h,rgba:out};}
const [outp,...ins]=process.argv.slice(2);const imgs=ins.map(readPNG);const cell=imgs[0].w,cols=Math.min(4,imgs.length),rows=Math.ceil(imgs.length/cols);
const W=cols*cell,H=rows*cell,o=new Uint8Array(W*H*4);for(let i=0;i<W*H;i++){o[i*4]=40;o[i*4+1]=44;o[i*4+2]=40;o[i*4+3]=255;}
imgs.forEach((im,k)=>{const ox=(k%cols)*cell,oy=Math.floor(k/cols)*cell;for(let y=0;y<im.h;y++)for(let x=0;x<im.w;x++){const s=(y*im.w+x)*4,a=im.rgba[s+3]/255,d=((oy+y)*W+ox+x)*4;for(let c=0;c<3;c++)o[d+c]=Math.round(im.rgba[s+c]*a+o[d+c]*(1-a));}});
fs.writeFileSync(outp,encodePNG(W,H,o));
