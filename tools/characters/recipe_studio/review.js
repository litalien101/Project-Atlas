const $ = (selector) => document.querySelector(selector);
const select = $("#model-select"), canvas = $("#canvas"), status = $("#status"), markerList = $("#marker-list");
const titleInput = $("#annotation-title"), noteInput = $("#annotation-note"), actionSelect = $("#action-select");
const COLORS = {feature:0xffc857,separate:0xff5d4a,reshape:0x63d9ed,smooth:0xb99aff,remove:0xf27b96};
let THREE, GLTFLoaderCtor, GLTFExporterCtor, OrbitControlsCtor, controls, renderer, scene, camera, grid, model, modelId, models = [];
let annotations = [], annotationObjects = new Map(), pendingTrace = [], traceLine, placing = null, pointerDown = null, dragTarget = null, dragAnchor = null, selectedId = null, radius = .01, modelSize = 1, upIsZ = true, moldEnabled = false, sculptSnapshot = null, modelChanged = false;
function say(message) { status.textContent = message; }
async function jsonRequest(url, options) {
  const response=await fetch(url,options),data=await response.json();
  if(!response.ok)throw new Error(data.error||`Request failed (${response.status})`);return data;
}
function initViewer() {
  renderer=new THREE.WebGLRenderer({canvas,antialias:true,alpha:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=0.85;
  scene=new THREE.Scene();scene.add(new THREE.HemisphereLight(0xe6ecd9,0x27352c,0.65));
  const key=new THREE.DirectionalLight(0xffe8c3,1.1);key.position.set(-3,-4,5);scene.add(key);
  const rim=new THREE.DirectionalLight(0xb4d99e,0.35);rim.position.set(3,2,3);scene.add(rim);
  camera=new THREE.PerspectiveCamera(36,1,.001,100);controls=new OrbitControlsCtor(camera,canvas);controls.enableDamping=true;
  grid=new THREE.GridHelper(3,30,0x657966,0x354239);scene.add(grid);
  const resize=()=>{const rect=canvas.getBoundingClientRect();if(!rect.width||!rect.height)return;renderer.setSize(rect.width,rect.height,false);camera.aspect=rect.width/rect.height;camera.updateProjectionMatrix();};
  new ResizeObserver(resize).observe(canvas.parentElement);resize();
  const draw=()=>{requestAnimationFrame(draw);controls.update();renderer.render(scene,camera);};draw();
}
function disposeVisual(object){scene.remove(object);object.geometry?.dispose();if(object.material){for(const material of Array.isArray(object.material)?object.material:[object.material]){material.map?.dispose();material.dispose();}}}
function annotationColor(item){return COLORS[item.action]||COLORS.feature;}
function lineObject(points,color,selected=false){
  const geometry=new THREE.BufferGeometry().setFromPoints(points.map(point=>new THREE.Vector3(...point)));
  const line=new THREE.Line(geometry,new THREE.LineBasicMaterial({color,depthTest:false,transparent:true,opacity:selected?1:.52}));line.renderOrder=19;scene.add(line);return line;
}
function beginSculpt(anchor){
  if(!moldEnabled||!model)return null;
  model.updateMatrixWorld(true);const influence=modelSize*.032,snapshot=[];
  model.traverse(mesh=>{if(!mesh.isMesh)return;const attribute=mesh.geometry.getAttribute("position");if(!attribute)return;const original=attribute.array.slice(),weights=[];
    const localToWorld=mesh.matrixWorld;
    for(let i=0;i<attribute.count;i++){const point=new THREE.Vector3(attribute.getX(i),attribute.getY(i),attribute.getZ(i)).applyMatrix4(localToWorld),distance=point.distanceTo(anchor);if(distance<influence*2){const weight=Math.exp(-.5*(distance/influence)**2);weights.push([i,weight]);}}
    if(weights.length)snapshot.push({mesh,attribute,original,weights,inverse:new THREE.Matrix3().setFromMatrix4(mesh.matrixWorld).invert()});
  });return snapshot;
}
function applySculpt(snapshot,worldDelta){
  if(!snapshot||!worldDelta.length())return;
  for(const entry of snapshot){const {attribute,original,weights,inverse}=entry,array=attribute.array;array.set(original);const delta=worldDelta.clone().applyMatrix3(inverse);
    for(const [index,weight] of weights){const offset=index*3;array[offset]+=delta.x*weight;array[offset+1]+=delta.y*weight;array[offset+2]+=delta.z*weight;}
    attribute.needsUpdate=true;entry.mesh.geometry.computeVertexNormals();entry.mesh.geometry.computeBoundingBox();entry.mesh.geometry.computeBoundingSphere();
  }
  modelChanged=true;$("#export-molded").disabled=false;
}
function drawAnnotation(item,index){
  const selected=item.id===selectedId,color=annotationColor(item),visuals=[];
  if(item.kind==="point"){
    const pin=new THREE.Mesh(new THREE.OctahedronGeometry(radius*.34,0),new THREE.MeshBasicMaterial({color,depthTest:false,transparent:true,opacity:selected?1:.78}));pin.position.fromArray(item.points[0]);pin.renderOrder=20;pin.userData={annotationId:item.id,pointIndex:0,draggable:true,handleVisual:true};scene.add(pin);visuals.push(pin);
    const hit=new THREE.Mesh(new THREE.SphereGeometry(radius*.9,8,6),new THREE.MeshBasicMaterial({transparent:true,opacity:0,depthTest:false}));hit.position.fromArray(item.points[0]);hit.userData={annotationId:item.id,pointIndex:0,draggable:true};scene.add(hit);visuals.push(hit);
  } else visuals.push(lineObject(item.points,color,selected));
  const anchor=item.points[Math.floor(item.points.length/2)],tagCanvas=document.createElement("canvas"),ctx=tagCanvas.getContext("2d");
  tagCanvas.width=selected?220:40;tagCanvas.height=40;ctx.fillStyle="rgba(15,21,18,.92)";ctx.beginPath();ctx.roundRect(2,2,tagCanvas.width-4,36,18);ctx.fill();
  ctx.strokeStyle=`#${color.toString(16).padStart(6,"0")}`;ctx.lineWidth=3;ctx.stroke();ctx.fillStyle="#f4f1e7";ctx.font=`bold ${selected?18:22}px sans-serif`;ctx.textAlign="center";ctx.textBaseline="middle";
  const shortTitle=item.title.replace(/^Character right hand /,"R · ").replace(/^Character left hand /,"L · ").replace("separate ","split ");ctx.fillText(selected?`${index+1} · ${shortTitle.slice(0,20)}`:String(index+1),tagCanvas.width/2,20);
  const texture=new THREE.CanvasTexture(tagCanvas);texture.colorSpace=THREE.SRGBColorSpace;
  const tag=new THREE.Sprite(new THREE.SpriteMaterial({map:texture,depthTest:false,transparent:true}));tag.position.fromArray(anchor);tag.position[upIsZ?2:1]+=radius*.8;tag.scale.set(radius*(selected ? 2.5 : 1.05),radius*(selected ? 0.72 : 0.46),1);tag.renderOrder=21;tag.userData={annotationId:item.id,isGuideTag:true};scene.add(tag);visuals.push(tag);
  if(!selected){
    if(item.kind==="polyline")for(const [pointIndex,point] of item.points.entries()){
      const node=new THREE.Mesh(new THREE.SphereGeometry(radius*.2,8,6),new THREE.MeshBasicMaterial({color,depthTest:false,transparent:true,opacity:.72}));node.position.fromArray(point);node.renderOrder=20;node.userData={annotationId:item.id,pointIndex,draggable:true,handleVisual:true};scene.add(node);visuals.push(node);
      const hit=new THREE.Mesh(new THREE.SphereGeometry(radius*.9,8,6),new THREE.MeshBasicMaterial({transparent:true,opacity:0,depthTest:false}));hit.position.fromArray(point);hit.userData={annotationId:item.id,pointIndex,draggable:true};scene.add(hit);visuals.push(hit);
    }
    annotationObjects.set(item.id,visuals);return;
  }
  if(item.kind==="polyline")for(const [pointIndex,point] of item.points.entries()){
    const node=new THREE.Mesh(new THREE.SphereGeometry(radius*.28,8,6),new THREE.MeshBasicMaterial({color,depthTest:false}));node.position.fromArray(point);node.renderOrder=20;node.userData={annotationId:item.id,pointIndex,draggable:true,handleVisual:true};scene.add(node);visuals.push(node);
    const hit=new THREE.Mesh(new THREE.SphereGeometry(radius*.9,8,6),new THREE.MeshBasicMaterial({transparent:true,opacity:0,depthTest:false}));hit.position.fromArray(point);hit.userData={annotationId:item.id,pointIndex,draggable:true};scene.add(hit);visuals.push(hit);
  }
  annotationObjects.set(item.id,visuals);
}
function renderAnnotations(){
  for(const objects of annotationObjects.values())for(const object of objects)disposeVisual(object);annotationObjects.clear();
  annotations.forEach(drawAnnotation);
  markerList.replaceChildren();
  if(!annotations.length){selectedId=null;$("#selected-controls").hidden=true;const empty=document.createElement("div");empty.className="empty";empty.textContent="No edit marks yet. Pin a finger, feature, or area to change.";markerList.append(empty);return;}
  annotations.forEach((item,index)=>{
    const row=document.createElement("article");row.className=`marker-row${selectedId===item.id?" selected":""}`;row.dataset.action=item.action;row.addEventListener("click",()=>selectAnnotation(item.id));
    const top=document.createElement("div");top.className="marker-top";
    const number=document.createElement("span");number.className="marker-number";number.textContent=String(index+1);
    const desc=document.createElement("div");desc.className="marker-text";desc.textContent=`${item.title} · ${item.action}`;
    top.append(number,desc);row.append(top);
    const note=document.createElement("div");note.className="coords";note.textContent=item.note||`${item.points.length} points`;row.append(note);
    const actions=document.createElement("div");actions.className="marker-actions";
    const focus=document.createElement("button");focus.type="button";focus.textContent="Focus";focus.addEventListener("click",()=>focusAnnotation(item));
    const remove=document.createElement("button");remove.type="button";remove.className="delete";remove.textContent="Delete";remove.addEventListener("click",()=>{annotations=annotations.filter(entry=>entry.id!==item.id);if(selectedId===item.id)selectedId=null;renderAnnotations();void saveAnnotations();});
    actions.append(focus,remove);row.append(actions);markerList.append(row);
  });
  const selected=annotations.find(item=>item.id===selectedId);
  $("#selected-controls").hidden=!selected;
  if(selected){$("#selected-label").textContent=`${selected.title} · drag a ${selected.kind==="point"?"pin":"path point"} on the model`;
    const isLine=selected.kind==="polyline";$("#add-path-point").hidden=!isLine;$("#remove-path-point").hidden=!isLine||selected.points.length<=2;}
}
function selectAnnotation(id){selectedId=id;renderAnnotations();say("Selected guide. Drag its pin or any path point to reposition it on the surface.");}
function focusAnnotation(item){const pos=item.points[Math.floor(item.points.length/2)],target=new THREE.Vector3(...pos),offset=camera.position.clone().sub(controls.target);controls.target.copy(target);camera.position.copy(target).add(offset);controls.update();}
function setView(view){if(!model)return;const target=controls.target.clone(),distance=camera.position.distanceTo(target),up=upIsZ?new THREE.Vector3(0,0,1):new THREE.Vector3(0,1,0),forward=upIsZ?new THREE.Vector3(0,-1,0):new THREE.Vector3(0,0,1);let direction,viewUp=up;
  if(view==="front")direction=forward;else if(view==="back")direction=forward.clone().negate();else if(view==="left")direction=new THREE.Vector3(-1,0,0);else if(view==="right")direction=new THREE.Vector3(1,0,0);else if(view==="top"){direction=up;viewUp=forward;}else{direction=up.clone().negate();viewUp=forward.clone().negate();}
  camera.up.copy(viewUp);camera.position.copy(target).addScaledVector(direction,distance);camera.lookAt(target);controls.update();}
async function saveAnnotations(){if(!modelId)return;try{await jsonRequest("/api/model-review/annotations",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({model_id:modelId,annotations})});say(`${annotations.length} edit mark${annotations.length===1?"":"s"} saved for ${modelId}.`);}catch(error){say(`Could not save edit guide: ${error.message}`);}}
function setMode(mode){placing=mode;if(mode!=="trace")clearTrace(false);$("#point-toggle").classList.toggle("active",mode==="point");$("#trace-toggle").classList.toggle("active",mode==="trace");$("#trace-actions").hidden=mode!=="trace";say(mode==="point"?"Click a point on the model surface.":mode==="trace"?"Click 2 or more points along the desired separation path.":"Ready.");}
function clearTrace(removeMode=true){pendingTrace=[];if(traceLine){disposeVisual(traceLine);traceLine=null;}$("#trace-count").textContent="Click points along the desired line";if(removeMode&&placing==="trace")setMode(null);}
function pointerRay(event){const rect=canvas.getBoundingClientRect(),pointer=new THREE.Vector2(((event.clientX-rect.left)/rect.width)*2-1,-((event.clientY-rect.top)/rect.height)*2+1),raycaster=new THREE.Raycaster();raycaster.setFromCamera(pointer,camera);return raycaster;}
function hitPoint(event){const hits=pointerRay(event).intersectObject(model,true);return hits[0]?.point.toArray().map(v=>Number(v.toFixed(6)))||null;}
function annotationHit(event){const ray=pointerRay(event),objects=[];for(const visuals of annotationObjects.values())for(const object of visuals)if(object.userData.annotationId)objects.push(object);const hits=ray.intersectObjects(objects,false);return hits.find(hit=>hit.object.userData.isGuideTag)?.object||hits[0]?.object||null;}
function validateEntry(){if(!titleInput.value.trim()){say("Give this edit mark a short label, such as Left index finger.");titleInput.focus();return false;}return true;}
function handleSurfaceClick(event){if(!placing||!model)return;const point=hitPoint(event);if(!point){say("Click directly on the model surface.");return;}
  if(placing==="add-path"){const item=annotations.find(entry=>entry.id===selectedId);if(!item||item.kind!=="polyline")return;if(item.points.length>=256){say("This guide has reached the 256-point limit.");return;}item.points.push(point);renderAnnotations();void saveAnnotations();say(`Added surface point (${item.points.length} along this guide).`);return;}
  if(!validateEntry())return;
  if(placing==="point"){
    annotations.push({id:crypto.randomUUID(),kind:"point",action:actionSelect.value,title:titleInput.value.trim(),note:noteInput.value.trim(),points:[point],created_at:new Date().toISOString()});
    titleInput.value="";noteInput.value="";setMode(null);renderAnnotations();void saveAnnotations();
  }else if(placing==="trace"){
    pendingTrace.push(point);$("#trace-count").textContent=`${pendingTrace.length} point${pendingTrace.length===1?"":"s"} on separation path`;
    if(traceLine)disposeVisual(traceLine);if(pendingTrace.length>1)traceLine=lineObject(pendingTrace,0xff5d4a);
  }
}
async function loadModel(id){const item=models.find(entry=>entry.id===id);if(!item)return;
  if(model)model.traverse(object=>{object.geometry?.dispose();if(object.material)for(const material of Array.isArray(object.material)?object.material:[object.material])material.dispose();});
  for(const child of [...scene.children])if(child.userData.reviewModel)scene.remove(child);
  setMode(null);modelId=id;model=null;annotations=[];selectedId=null;renderAnnotations();$("#loading").hidden=false;say(`Loading ${item.label}…`);
  try{
    const loader=new GLTFLoaderCtor();const gltf=await new Promise((resolve,reject)=>loader.load(item.url,resolve,progress=>{const message=progress.total?`Loading ${item.label}… ${Math.round(progress.loaded/progress.total*100)}%`:`Loading ${item.label}… ${(progress.loaded/1048576).toFixed(1)} MB`;say(message);$("#loading").textContent=message;},reject));
    model=gltf.scene;model.userData.reviewModel=true;let texturedMaterials=0,normalMappedMaterials=0;model.traverse(object=>{if(object.isMesh){object.geometry=object.geometry.clone();for(const material of Array.isArray(object.material)?object.material:[object.material]){if(material.map){material.map.colorSpace=THREE.SRGBColorSpace;material.map.needsUpdate=true;texturedMaterials++;}if(material.normalMap){normalMappedMaterials++;}}}});const bounds=new THREE.Box3().setFromObject(model),center=bounds.getCenter(new THREE.Vector3()),size=bounds.getSize(new THREE.Vector3());model.position.sub(center);model.updateMatrixWorld(true);scene.add(model);modelChanged=false;$("#export-molded").disabled=true;
    const maxDim=Math.max(size.x,size.y,size.z);modelSize=maxDim;radius=maxDim*.012;upIsZ=size.z>size.y;camera.up.set(0,upIsZ?0:1,upIsZ?1:0);grid.rotation.x=upIsZ?Math.PI/2:0;
    camera.position.set(maxDim*1.15,upIsZ?-maxDim*2.5:maxDim*.85,upIsZ?maxDim*.85:maxDim*2.5);camera.near=maxDim/1000;camera.far=maxDim*100;camera.updateProjectionMatrix();controls.target.set(0,0,0);controls.minDistance=maxDim*.3;controls.maxDistance=maxDim*8;controls.update();
    const saved=await jsonRequest(`/api/model-review/annotations?model_id=${encodeURIComponent(id)}`);annotations=(saved.annotations||[]);renderAnnotations();$("#blend-link").href=`/api/model-review/blend?model_id=${encodeURIComponent(id)}`;say(`${item.label} · ${texturedMaterials} base-color map${texturedMaterials===1?"":"s"}, ${normalMappedMaterials} normal map${normalMappedMaterials===1?"":"s"} loaded · ${annotations.length} edit marks.`);
  }catch(error){say(`Could not load model: ${error.message}`);}finally{$("#loading").hidden=true;}
}
canvas.addEventListener("pointerdown",event=>{pointerDown={x:event.clientX,y:event.clientY};const hit=annotationHit(event);if(hit){selectAnnotation(hit.userData.annotationId);if(hit.userData.draggable){dragTarget=hit.userData;const item=annotations.find(entry=>entry.id===dragTarget.annotationId),position=item?.points[dragTarget.pointIndex];dragAnchor=position?new THREE.Vector3(...position):null;sculptSnapshot=dragAnchor?beginSculpt(dragAnchor):null;controls.enabled=false;canvas.setPointerCapture(event.pointerId);event.preventDefault();}}});
canvas.addEventListener("pointermove",event=>{if(!dragTarget)return;const point=hitPoint(event);if(!point)return;const item=annotations.find(entry=>entry.id===dragTarget.annotationId);if(!item)return;const next=new THREE.Vector3(...point);if(sculptSnapshot&&dragAnchor)applySculpt(sculptSnapshot,next.clone().sub(dragAnchor));item.points[dragTarget.pointIndex]=point;const visuals=annotationObjects.get(item.id),handle=visuals.find(object=>object.userData.handleVisual&&object.userData.pointIndex===dragTarget.pointIndex);if(handle)handle.position.copy(next);if(item.kind==="polyline"){visuals[0].geometry.dispose();visuals[0].geometry=new THREE.BufferGeometry().setFromPoints(item.points.map(value=>new THREE.Vector3(...value)));const tag=visuals.find(object=>object.userData.isGuideTag);if(tag){tag.position.fromArray(item.points[Math.floor(item.points.length/2)]);tag.position[upIsZ?2:1]+=radius*.8;}}});
canvas.addEventListener("pointerup",event=>{if(dragTarget){dragTarget=null;dragAnchor=null;sculptSnapshot=null;controls.enabled=true;renderAnnotations();void saveAnnotations();say(moldEnabled?"Hand surface and control position updated; export a GLB to keep the molded mesh.":"Guide point moved and saved to the model surface.");}else if(pointerDown&&Math.hypot(event.clientX-pointerDown.x,event.clientY-pointerDown.y)<5)handleSurfaceClick(event);pointerDown=null;});
canvas.addEventListener("pointercancel",()=>{if(dragTarget){dragTarget=null;dragAnchor=null;sculptSnapshot=null;controls.enabled=true;renderAnnotations();}});
$("#point-toggle").addEventListener("click",()=>setMode(placing==="point"?null:"point"));
$("#trace-toggle").addEventListener("click",()=>{if(!validateEntry())return;actionSelect.value="separate";setMode(placing==="trace"?null:"trace");});
$("#undo-trace").addEventListener("click",()=>{pendingTrace.pop();if(traceLine)disposeVisual(traceLine);traceLine=pendingTrace.length>1?lineObject(pendingTrace,0xff5d4a):null;$("#trace-count").textContent=`${pendingTrace.length} point${pendingTrace.length===1?"":"s"} on separation path`;});
$("#cancel-trace").addEventListener("click",()=>clearTrace(true));
$("#add-path-point").addEventListener("click",()=>{if(!annotations.some(item=>item.id===selectedId&&item.kind==="polyline"))return;placing=placing==="add-path"?null:"add-path";$("#add-path-point").classList.toggle("active",placing==="add-path");say(placing==="add-path"?"Orbit to the side or back, then click the model to add a surface point to the selected guide.":"Ready.");});
$("#remove-path-point").addEventListener("click",()=>{const item=annotations.find(entry=>entry.id===selectedId&&entry.kind==="polyline");if(!item||item.points.length<=2)return;item.points.pop();renderAnnotations();void saveAnnotations();say("Last guide point removed.");});
$("#mold-toggle").addEventListener("click",event=>{moldEnabled=!moldEnabled;event.currentTarget.setAttribute("aria-pressed",String(moldEnabled));event.currentTarget.classList.toggle("active",moldEnabled);event.currentTarget.textContent=`Mold surface: ${moldEnabled?"on":"off"}`;say(moldEnabled?"Mold mode is on. Drag a pin or trace point; nearby mesh vertices will follow smoothly.":"Mold mode is off. Dragging changes guide points only.");});
$("#export-molded").addEventListener("click",()=>{if(!modelChanged||!model){say("Move a hand control in mold mode before exporting.");return;}const exporter=new GLTFExporterCtor();exporter.parse(model,result=>{const blob=new Blob([result],{type:"model/gltf-binary"}),url=URL.createObjectURL(blob),link=document.createElement("a");link.href=url;link.download=`${modelId}-hand-molded.glb`;link.click();URL.revokeObjectURL(url);say("Exported a molded GLB copy.");},error=>say(`Could not export GLB: ${error.message}`),{binary:true});});
document.querySelectorAll("[data-view]").forEach(button=>button.addEventListener("click",()=>setView(button.dataset.view)));
$("#pan-toggle").addEventListener("click",event=>{const active=event.currentTarget.getAttribute("aria-pressed")==="true";event.currentTarget.setAttribute("aria-pressed",String(!active));event.currentTarget.classList.toggle("active",!active);controls.mouseButtons.LEFT=active?THREE.MOUSE.ROTATE:THREE.MOUSE.PAN;say(active?"Orbit mode: drag to rotate the model.":"Pan mode: drag to move the view across the model.");});
$("#finish-trace").addEventListener("click",()=>{if(pendingTrace.length<2){say("Place at least two points along the separation path.");return;}if(!validateEntry())return;annotations.push({id:crypto.randomUUID(),kind:"polyline",action:"separate",title:titleInput.value.trim(),note:noteInput.value.trim(),points:[...pendingTrace],created_at:new Date().toISOString()});titleInput.value="";noteInput.value="";setMode(null);renderAnnotations();void saveAnnotations();});
select.addEventListener("change",()=>void loadModel(select.value));
$("#export-markers").addEventListener("click",()=>{const data={schema:"atlas-model-edit-guide/v1",model_id:modelId,annotations};const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:"application/json"}));const link=document.createElement("a");link.href=url;link.download=`${modelId}-edit-guide.json`;link.click();URL.revokeObjectURL(url);});
try{
  const [threeModule,{OrbitControls},{GLTFLoader},{GLTFExporter}]=await Promise.all([import("three"),import("three/addons/controls/OrbitControls.js"),import("three/addons/loaders/GLTFLoader.js"),import("three/addons/exporters/GLTFExporter.js")]);THREE=threeModule;GLTFLoaderCtor=GLTFLoader;GLTFExporterCtor=GLTFExporter;OrbitControlsCtor=OrbitControls;initViewer();
  const response=await jsonRequest("/api/model-review/models");models=response.models||[];
  for(const item of models){const option=document.createElement("option");option.value=item.id;option.textContent=`${item.label} · ${(item.size_bytes/1048576).toFixed(1)} MB`;select.append(option);}
  if(!models.length){say("No review models were found.");$("#loading").hidden=true;}else{const requestedId=new URLSearchParams(location.search).get("model");const initial=models.find(item=>item.id===requestedId)||models.find(item=>item.id==="appearance-r002-mottled-hide")||models.find(item=>item.id==="r003")||models[0];select.value=initial.id;await loadModel(initial.id);}
}catch(error){$("#loading").textContent=`Viewer failed to start: ${error.message}`;say(error.message);}
