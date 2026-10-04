const $ = (selector) => document.querySelector(selector);
const select = $("#model-select"), canvas = $("#canvas"), status = $("#status");
const markerNote = $("#marker-note"), markerList = $("#marker-list");
let THREE, GLTFLoaderCtor, controls, renderer, scene, camera, grid, model, modelId, models = [], markers = [], markerObjects = new Map();
let placing = false, selectedMarker = null, down = null, frame = 0, radius = 0.01;

function say(message) { status.textContent = message; }
async function jsonRequest(url, options) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}

function initViewer() {
  renderer = new THREE.WebGLRenderer({canvas, antialias:true, alpha:true});
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  scene = new THREE.Scene();
  scene.add(new THREE.HemisphereLight(0xe6ecd9, 0x27352c, 2.2));
  const key = new THREE.DirectionalLight(0xffe8c3, 3); key.position.set(-3,-4,5); scene.add(key);
  const rim = new THREE.DirectionalLight(0xb4d99e, 1.5); rim.position.set(3,2,3); scene.add(rim);
  camera = new THREE.PerspectiveCamera(36, 1, 0.001, 100);
  controls = new (window.OrbitControlsClass)(camera, canvas);
  controls.enableDamping = true;
  controls.target.set(0,0,0);
  grid=new THREE.GridHelper(3,30,0x657966,0x354239); scene.add(grid);
  const resize = () => {
    const rect = canvas.getBoundingClientRect(); if (!rect.width || !rect.height) return;
    renderer.setSize(rect.width, rect.height, false); camera.aspect = rect.width/rect.height; camera.updateProjectionMatrix();
  };
  new ResizeObserver(resize).observe(canvas.parentElement); resize();
  const draw = () => { frame=requestAnimationFrame(draw); controls.update(); renderer.render(scene,camera); };
  draw();
}

function markerSphere(marker, index) {
  const geometry = new THREE.SphereGeometry(radius, 16, 12);
  const material = new THREE.MeshBasicMaterial({color: marker.id === selectedMarker ? 0xfff08a : 0xf0523c, depthTest:false});
  const sphere = new THREE.Mesh(geometry, material);
  sphere.position.fromArray(marker.position); sphere.renderOrder = 20; sphere.userData.markerId = marker.id;
  scene.add(sphere); markerObjects.set(marker.id, sphere);
}
function renderMarkers() {
  for (const object of markerObjects.values()) { scene.remove(object); object.geometry.dispose(); object.material.dispose(); }
  markerObjects.clear(); markers.forEach((marker,index)=>markerSphere(marker,index));
  markerList.replaceChildren();
  if (!markers.length) { const empty=document.createElement("div"); empty.className="empty"; empty.textContent="No markers yet. Add a note, then click Place marker and click the model."; markerList.append(empty); return; }
  markers.forEach((marker,index)=>{
    const row=document.createElement("article"); row.className=`marker-row${selectedMarker===marker.id?" selected":""}`;
    const top=document.createElement("div"); top.className="marker-top";
    const number=document.createElement("span"); number.className="marker-number"; number.textContent=String(index+1);
    const note=document.createElement("div"); note.className="marker-text"; note.textContent=marker.note;
    top.append(number,note);
    const coords=document.createElement("div"); coords.className="coords"; coords.textContent=`x ${marker.position[0].toFixed(4)} · y ${marker.position[1].toFixed(4)} · z ${marker.position[2].toFixed(4)}`;
    const actions=document.createElement("div"); actions.className="marker-actions";
    const focus=document.createElement("button"); focus.type="button"; focus.textContent="Focus"; focus.addEventListener("click",()=>focusMarker(marker));
    const remove=document.createElement("button"); remove.type="button"; remove.className="delete"; remove.textContent="Delete"; remove.addEventListener("click",()=>{markers=markers.filter(item=>item.id!==marker.id);if(selectedMarker===marker.id)selectedMarker=null;renderMarkers();void saveMarkers();});
    actions.append(focus,remove); row.append(top,coords,actions); markerList.append(row);
  });
}
function focusMarker(marker) {
  selectedMarker=marker.id; const point=new THREE.Vector3(...marker.position); const offset=camera.position.clone().sub(controls.target);
  controls.target.copy(point); camera.position.copy(point).add(offset); controls.update(); renderMarkers();
}
async function saveMarkers() {
  if (!modelId) return;
  try { await jsonRequest("/api/model-review/annotations",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({model_id:modelId,markers})}); say(`${markers.length} marker${markers.length===1?"":"s"} saved for ${modelId}.`); }
  catch(error){say(`Could not save markers: ${error.message}`);}
}
async function loadModel(id) {
  const item=models.find(entry=>entry.id===id); if(!item)return;
  if(model) model.traverse(object=>{if(object.geometry)object.geometry.dispose();if(object.material){for(const material of Array.isArray(object.material)?object.material:[object.material])material.dispose();}});
  modelId=id; model=null; markers=[]; selectedMarker=null; markerObjects.clear();
  for(const child of [...scene.children]) if(child.userData.reviewModel||child.userData.markerId){scene.remove(child);}
  $("#loading").hidden=false; say(`Loading ${item.label}…`); renderMarkers();
  try {
    const loader=new GLTFLoaderCtor();
    const gltf=await new Promise((resolve,reject)=>loader.load(item.url,resolve,(progress)=>{
      if(progress.total) say(`Loading ${item.label}… ${Math.round(progress.loaded/progress.total*100)}%`);
      else say(`Loading ${item.label}… ${(progress.loaded/1048576).toFixed(1)} MB`);
    },reject));
    model=gltf.scene; model.userData.reviewModel=true;
    const bounds=new THREE.Box3().setFromObject(model), center=bounds.getCenter(new THREE.Vector3()), size=bounds.getSize(new THREE.Vector3());
    model.position.sub(center); model.updateMatrixWorld(true); scene.add(model);
    const maxDim=Math.max(size.x,size.y,size.z); radius=maxDim*.012;
    const zUp=size.z>size.y;
    camera.up.set(0,zUp?0:1,zUp?1:0);
    grid.rotation.x=zUp?Math.PI/2:0;
    camera.position.set(maxDim*1.15,zUp?-maxDim*2.5:maxDim*.85,zUp?maxDim*.85:-maxDim*2.5); camera.near=maxDim/1000; camera.far=maxDim*100; camera.updateProjectionMatrix();
    controls.target.set(0,0,0); controls.minDistance=maxDim*.3; controls.maxDistance=maxDim*8; controls.update();
    const saved=await jsonRequest(`/api/model-review/annotations?model_id=${encodeURIComponent(id)}`); markers=Array.isArray(saved.markers)?saved.markers:[];
    renderMarkers(); $("#blend-link").href=`/api/model-review/blend?model_id=${encodeURIComponent(id)}`;
    say(`${item.label} · ${markers.length} saved marker${markers.length===1?"":"s"}. Click Place marker, then click a surface.`);
  } catch(error){say(`Could not load model: ${error.message}`);}
  finally{$("#loading").hidden=true;}
}

function placeAtPointer(event) {
  if(!placing||!model)return;
  const note=markerNote.value.trim(); if(!note){say("Add a short note before placing a marker.");markerNote.focus();return;}
  const rect=canvas.getBoundingClientRect(); const pointer=new THREE.Vector2(((event.clientX-rect.left)/rect.width)*2-1,-((event.clientY-rect.top)/rect.height)*2+1);
  const raycaster=new THREE.Raycaster(); raycaster.setFromCamera(pointer,camera); const hits=raycaster.intersectObject(model,true);
  if(!hits.length){say("No model surface at that point. Click directly on the model.");return;}
  const marker={id:crypto.randomUUID(),position:hits[0].point.toArray().map(v=>Number(v.toFixed(6))),note,created_at:new Date().toISOString()};
  markers.push(marker);markerNote.value="";selectedMarker=marker.id;placing=false;$("#place-toggle").classList.remove("active");$("#place-toggle").textContent="Place marker";renderMarkers();void saveMarkers();
}

canvas.addEventListener("pointerdown",event=>{down={x:event.clientX,y:event.clientY};});
canvas.addEventListener("pointerup",event=>{if(down&&Math.hypot(event.clientX-down.x,event.clientY-down.y)<5)placeAtPointer(event);down=null;});
$("#place-toggle").addEventListener("click",()=>{if(!markerNote.value.trim()){say("Add a short note before placing a marker.");markerNote.focus();return;}placing=!placing;$("#place-toggle").classList.toggle("active",placing);$("#place-toggle").textContent=placing?"Cancel marker":"Place marker";say(placing?"Click a point on the model to place the marker.":"Marker placement cancelled.");});
select.addEventListener("change",()=>void loadModel(select.value));
$("#export-markers").addEventListener("click",()=>{const blob=new Blob([JSON.stringify({schema:"atlas-model-review/v1",model_id:modelId,markers},null,2)],{type:"application/json"});const url=URL.createObjectURL(blob);const link=document.createElement("a");link.href=url;link.download=`${modelId}-markers.json`;link.click();URL.revokeObjectURL(url);});

try {
  const [threeModule, {OrbitControls}, {GLTFLoader}]=await Promise.all([import("three"),import("three/addons/controls/OrbitControls.js"),import("three/addons/loaders/GLTFLoader.js")]);
  THREE=threeModule; GLTFLoaderCtor=GLTFLoader;
  window.OrbitControlsClass=OrbitControls; window.THREE=THREE;
  initViewer(); const response=await jsonRequest("/api/model-review/models"); models=response.models||[];
  for(const item of models){const option=document.createElement("option");option.value=item.id;option.textContent=`${item.label} · ${(item.size_bytes/1048576).toFixed(1)} MB`;select.append(option);}
  if(!models.length){say("No review models were found.");$("#loading").hidden=true;}else {
    const initial=models.find(item=>item.id==="r003")||models[0];
    select.value=initial.id;
    await loadModel(initial.id);
  }
} catch(error){$("#loading").textContent=`Viewer failed to start: ${error.message}`;say(error.message);}
