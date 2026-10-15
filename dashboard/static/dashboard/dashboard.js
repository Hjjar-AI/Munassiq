/* Progressive enhancement: forms and confirmations also work without JavaScript. */
const ar=document.documentElement.lang==='ar';
const text=(a,e)=>ar?a:e;
let pendingUploads=0;
document.querySelectorAll('[name=image_files],[name=pdf_file],[name=photo_file]').forEach(input=>input.addEventListener('change',async()=>{
  const form=input.form,submit=form.querySelector('button.primary'),status=form.querySelector('[data-upload-status]');
  pendingUploads++;submit.disabled=true;
  try{
    for(const file of input.files){
      if(file.size>5*1024*1024)throw Error(text('الحد الأقصى لكل ملف 5 ميغابايت','Each file must be at most 5 MB'));
      status.textContent=text('جارٍ رفع الملفات…','Uploading files…');
      const data=new FormData();data.append('file',file);
      const response=await fetch('/dashboard/upload/'+(input.name==='pdf_file'?'event-pdfs':'images')+'/',{method:'POST',body:data,headers:{'X-CSRFToken':form.querySelector('[name=csrfmiddlewaretoken]').value}});
      const result=await response.json();if(!response.ok)throw Error(JSON.stringify(result));
      if(input.name==='image_files'){const hidden=document.createElement('input');hidden.type='hidden';hidden.name='new_image_id';hidden.value=result.id;form.append(hidden);}
      else form.querySelector('[name='+(input.name==='pdf_file'?'pdf_id':'photo_id')+']').value=result.id;
    }
    input.value='';status.textContent=text('تم رفع الملفات. احفظ النموذج لإرفاقها بالمحتوى.','Files uploaded. Save the form to attach them.');
  }catch(error){input.value='';status.textContent=text('تعذر رفع الملف: ','Upload failed: ')+error.message;}
  finally{pendingUploads--;submit.disabled=pendingUploads>0;}
}));
const city=document.querySelector('[name=city_id],[name=city]');
const country=document.querySelector('[name=country_id],[name=country],[name=country_id]');
let cityAbort;
async function loadCities(){
  if(!city)return;
  cityAbort?.abort();cityAbort=new AbortController();
  const params=new URLSearchParams({q:document.querySelector('[data-city-query]')?.value||''});
  if(country?.value)params.set('country',country.value);
  try{
    const response=await fetch('/dashboard/locations/?'+params,{signal:cityAbort.signal});
    if(!response.ok)throw Error();
    const rows=await response.json();
    const previous=city.value;city.replaceChildren(new Option(text('اختر المدينة','Choose city'),''));
    for(const row of rows)city.add(new Option(ar?row.name_ar:row.name_en,row.id));
    if([...city.options].some(option=>option.value===previous))city.value=previous;
  }catch(error){if(error.name!=='AbortError'){const message=document.querySelector('[data-city-query]');if(message)message.setCustomValidity(text('تعذر تحميل المدن. أعد المحاولة.','Could not load cities. Try again.'));}}
}
country?.addEventListener('change',()=>{if(city)city.value='';loadCities();});
let timer;
document.querySelector('[data-city-query]')?.addEventListener('input',event=>{event.target.setCustomValidity('');clearTimeout(timer);timer=setTimeout(loadCities,300);});
document.querySelector('[data-add-hour]')?.addEventListener('click',()=>document.querySelector('[data-hours]').append(document.querySelector('#hour-template').content.cloneNode(true)));
document.addEventListener('click',event=>{if(event.target.matches('[data-remove-hour]'))event.target.closest('.hours-row').remove();});
document.querySelectorAll('[data-local-time]').forEach(element=>{const date=new Date(element.dataset.localTime);if(!Number.isNaN(date.valueOf()))element.textContent=new Intl.DateTimeFormat(undefined,{dateStyle:'medium',timeStyle:'short',timeZoneName:undefined}).format(date);});
document.querySelectorAll('[data-copy]').forEach(button=>button.addEventListener('click',async()=>{try{await navigator.clipboard.writeText(button.dataset.copy);button.textContent=text('تم النسخ','Copied');}catch{window.prompt(text('انسخ العنوان','Copy address'),button.dataset.copy);}}));
document.querySelector('[data-share]')?.addEventListener('click',async event=>{try{const data={title:event.currentTarget.dataset.title,text:event.currentTarget.dataset.title,url:location.href};if(navigator.share)await navigator.share(data);else{await navigator.clipboard.writeText(data.text+' '+data.url);event.currentTarget.textContent=text('تم نسخ الرابط','Link copied');}}catch{}});
const map=document.querySelector('[data-map]');
if(map){
  const latitude=document.querySelector('[name=latitude]'),longitude=document.querySelector('[name=longitude]');
  let lat=Number(latitude?.value)||33.5138,lon=Number(longitude?.value)||36.2765,zoom=11,points=[];
  const project=(la,lo)=>{const size=256*2**zoom;const s=Math.sin(Math.max(-85.05,Math.min(85.05,la))*Math.PI/180);return[(lo+180)/360*size,(.5-Math.log((1+s)/(1-s))/(4*Math.PI))*size];};
  const unproject=(x,y)=>{const size=256*2**zoom;return[Math.atan(Math.sinh(Math.PI*(1-2*y/size)))*180/Math.PI,x/size*360-180];};
  function draw(){
    map.replaceChildren();const width=map.clientWidth,height=map.clientHeight,[cx,cy]=project(lat,lon),left=cx-width/2,top=cy-height/2;
    if(map.dataset.tiles){for(let x=Math.floor(left/256);x<Math.ceil((left+width)/256);x++)for(let y=Math.floor(top/256);y<Math.ceil((top+height)/256);y++){
      if(y<0||y>=2**zoom)continue;
      const image=document.createElement('img');image.alt='';image.draggable=false;image.src=map.dataset.tiles.replace('{z}',zoom).replace('{x}',((x%2**zoom)+2**zoom)%2**zoom).replace('{y}',y);image.style.left=x*256-left+'px';image.style.top=y*256-top+'px';map.append(image);
      image.onerror=()=>{document.querySelector('[data-map-status]').textContent=text('تعذر تحميل بعض مربعات الخريطة. الإحداثيات ما زالت متاحة.','Some map tiles could not load. Coordinate entry remains available.');};
    }}else document.querySelector('[data-map-status]').textContent=text('خريطة غير متاحة حالياً. يمكنك إدخال الإحداثيات.','Map unavailable. You can enter coordinates.');
    const clusters=new Map();
    for(const point of points){const [x,y]=project(point.latitude,point.longitude);const px=x-left,py=y-top;if(px<0||py<0||px>width||py>height)continue;const key=Math.floor(px/40)+':'+Math.floor(py/40);const group=clusters.get(key)||[];group.push({...point,x:px,y:py});clusters.set(key,group);}
    for(const group of clusters.values()){
      const point=group[0],pin=document.createElement('button');pin.type='button';pin.className='pin';pin.style.left=point.x+'px';pin.style.top=point.y+'px';pin.textContent=group.length>1?group.length:'•';pin.title=group.length>1?text('تكبير المجموعة','Zoom into cluster'):point.name;
      pin.addEventListener('click',event=>{event.stopPropagation();if(group.length>1&&zoom<18){lat=point.latitude;lon=point.longitude;zoom=Math.min(18,zoom+2);draw();}else if(group.length>1){const status=document.querySelector('[data-map-status]');status.replaceChildren();for(const entry of group){const link=document.createElement('a');link.href='/dashboard/items/service/'+entry.id+'/';link.textContent=entry.name;status.append(link,document.createElement('br'));}}else location.href='/dashboard/items/service/'+point.id+'/';});map.append(pin);
    }
    if(map.dataset.picker==='true'&&latitude?.value&&longitude?.value){const[x,y]=project(Number(latitude.value),Number(longitude.value));const pin=document.createElement('span');pin.className='pin';pin.style.background='#176b61';pin.style.color='white';pin.style.left=x-left+'px';pin.style.top=y-top+'px';pin.textContent='✓';map.append(pin);}
  }
  map.addEventListener('click',event=>{if(map.dataset.picker!=='true')return;const rect=map.getBoundingClientRect(),[cx,cy]=project(lat,lon);const[la,lo]=unproject(cx-rect.width/2+event.clientX-rect.left,cy-rect.height/2+event.clientY-rect.top);latitude.value=la.toFixed(6);longitude.value=(((lo+180)%360+360)%360-180).toFixed(6);draw();});
  document.querySelectorAll('[data-map-zoom]').forEach(button=>button.addEventListener('click',()=>{zoom=Math.max(2,Math.min(18,zoom+Number(button.dataset.mapZoom)));draw();}));
  document.querySelectorAll('[data-map-pan]').forEach(button=>button.addEventListener('click',()=>{const[dx,dy]=button.dataset.mapPan.split(',').map(Number),[x,y]=project(lat,lon);[lat,lon]=unproject(x+dx*150,y+dy*150);lat=Math.max(-85,Math.min(85,lat));lon=((lon+180)%360+360)%360-180;draw();}));
  for(const field of [latitude,longitude])field?.addEventListener('change',()=>{lat=Number(latitude.value)||lat;lon=Number(longitude.value)||lon;draw();});
  new ResizeObserver(draw).observe(map);draw();
  if(map.dataset.picker!=='true'){
    (async()=>{let page=1;try{while(page){const response=await fetch('/dashboard/markers/?page='+page);if(!response.ok)throw Error();const data=await response.json();points.push(...data.results.map(row=>({id:row.id,...row.payload})));page=data.next_page;}if(points.length){lat=points[0].latitude;lon=points[0].longitude;}draw();}catch{document.querySelector('[data-map-status]').textContent=text('تعذر تحميل نقاط الخدمة. أعد تحميل الصفحة للمحاولة.','Could not load services. Reload to retry.');}})();
  }
}
