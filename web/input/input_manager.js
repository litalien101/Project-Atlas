const CONTROL_KEYS = new Set([
  'w', 'a', 's', 'd', 'shift', ' ',
  'arrowup', 'arrowdown', 'arrowleft', 'arrowright',
]);

export class InputManager {
  constructor(canvas) {
    this.canvas = canvas;
    this.held = new Set();
    this.pressed = new Set();
    this.drag = null;
    this.mouseDelta = { x: 0, y: 0 };
    this.onKeyDown = event => {
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName)) return;
      const key = event.key.toLowerCase();
      if (!CONTROL_KEYS.has(key)) return;
      event.preventDefault();
      if (!this.held.has(key)) this.pressed.add(key);
      this.held.add(key);
    };
    this.onKeyUp = event => {
      const key = event.key.toLowerCase();
      this.held.delete(key);
      this.pressed.delete(key);
    };
    this.onBlur = () => { this.held.clear(); this.pressed.clear(); this.drag = null; };
    this.onPointerDown = event => {
      if (event.button !== 1 && event.button !== 2) return;
      event.preventDefault();
      this.drag = { pointerId: event.pointerId, x: event.clientX, y: event.clientY };
      canvas.setPointerCapture(event.pointerId);
    };
    this.onPointerMove = event => {
      if (!this.drag || event.pointerId !== this.drag.pointerId) return;
      this.mouseDelta.x += event.clientX - this.drag.x;
      this.mouseDelta.y += event.clientY - this.drag.y;
      this.drag.x = event.clientX;
      this.drag.y = event.clientY;
    };
    this.onPointerUp = event => { if (this.drag?.pointerId === event.pointerId) this.drag = null; };
    this.onContextMenu = event => { if (event.target === canvas) event.preventDefault(); };
    this.onWheel = event => {
      event.preventDefault();
      this.onZoom?.(event.deltaY);
    };
    window.addEventListener('keydown', this.onKeyDown);
    window.addEventListener('keyup', this.onKeyUp);
    window.addEventListener('blur', this.onBlur);
    canvas.addEventListener('pointerdown', this.onPointerDown);
    canvas.addEventListener('pointermove', this.onPointerMove);
    canvas.addEventListener('pointerup', this.onPointerUp);
    canvas.addEventListener('pointercancel', this.onPointerUp);
    canvas.addEventListener('contextmenu', this.onContextMenu);
    canvas.addEventListener('wheel', this.onWheel, { passive: false });
  }

  isDown(key) { return this.held.has(key); }
  justPressed(key) { const wasPressed = this.pressed.has(key); this.pressed.delete(key); return wasPressed; }
  movement() {
    return {
      forward: Number(this.isDown('w')) - Number(this.isDown('s')),
      strafe: Number(this.isDown('d')) - Number(this.isDown('a')),
      run: this.isDown('shift'),
    };
  }
  cameraIntent() {
    const result = {
      yaw: Number(this.isDown('arrowright')) - Number(this.isDown('arrowleft')),
      pitch: Number(this.isDown('arrowup')) - Number(this.isDown('arrowdown')),
      mouseX: this.mouseDelta.x,
      mouseY: this.mouseDelta.y,
    };
    this.mouseDelta.x = 0;
    this.mouseDelta.y = 0;
    return result;
  }
  setZoomHandler(handler) { this.onZoom = handler; }
}
