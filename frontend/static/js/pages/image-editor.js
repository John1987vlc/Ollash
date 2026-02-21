/**
 * Multimedia Artifact Image Editor (F14)
 * Canvas-based image editing for artifact previews.
 */

class ImageEditor {
    constructor(canvasId, imageUrl) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        this.image = new Image();
        this.history = [];
        this.historyIndex = -1;
        this.annotations = [];

        if (imageUrl) {
            this.loadImage(imageUrl);
        }
    }

    loadImage(url) {
        return new Promise((resolve, reject) => {
            this.image.crossOrigin = 'anonymous';
            this.image.onload = () => {
                this.canvas.width = this.image.width;
                this.canvas.height = this.image.height;
                this._drawImage();
                this._saveState();
                resolve();
            };
            this.image.onerror = reject;
            this.image.src = url;
        });
    }

    _drawImage() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        this.ctx.drawImage(this.image, 0, 0);
        this._drawAnnotations();
    }

    _drawAnnotations() {
        for (const ann of this.annotations) {
            this.ctx.save();
            this.ctx.font = ann.style?.font || '14px sans-serif';
            this.ctx.fillStyle = ann.style?.color || '#ff0';
            this.ctx.fillText(ann.text, ann.pos.x, ann.pos.y);
            this.ctx.restore();
        }
    }

    _saveState() {
        const data = this.canvas.toDataURL();
        this.history = this.history.slice(0, this.historyIndex + 1);
        this.history.push(data);
        this.historyIndex = this.history.length - 1;
    }

    crop(x, y, w, h) {
        const imageData = this.ctx.getImageData(x, y, w, h);
        this.canvas.width = w;
        this.canvas.height = h;
        this.ctx.putImageData(imageData, 0, 0);
        this._saveState();
    }

    resize(w, h) {
        const tempCanvas = document.createElement('canvas');
        tempCanvas.width = this.canvas.width;
        tempCanvas.height = this.canvas.height;
        tempCanvas.getContext('2d').drawImage(this.canvas, 0, 0);

        this.canvas.width = w;
        this.canvas.height = h;
        this.ctx.drawImage(tempCanvas, 0, 0, w, h);
        this._saveState();
    }

    annotate(text, pos, style) {
        this.annotations.push({ text, pos, style });
        this._drawImage();
        this._saveState();
    }

    applyFilter(filterName) {
        const imageData = this.ctx.getImageData(0, 0, this.canvas.width, this.canvas.height);
        const data = imageData.data;

        switch (filterName) {
            case 'grayscale':
                for (let i = 0; i < data.length; i += 4) {
                    const avg = (data[i] + data[i + 1] + data[i + 2]) / 3;
                    data[i] = data[i + 1] = data[i + 2] = avg;
                }
                break;
            case 'brightness':
                for (let i = 0; i < data.length; i += 4) {
                    data[i] = Math.min(255, data[i] + 30);
                    data[i + 1] = Math.min(255, data[i + 1] + 30);
                    data[i + 2] = Math.min(255, data[i + 2] + 30);
                }
                break;
            case 'contrast':
                const factor = 1.3;
                for (let i = 0; i < data.length; i += 4) {
                    data[i] = Math.min(255, Math.max(0, factor * (data[i] - 128) + 128));
                    data[i + 1] = Math.min(255, Math.max(0, factor * (data[i + 1] - 128) + 128));
                    data[i + 2] = Math.min(255, Math.max(0, factor * (data[i + 2] - 128) + 128));
                }
                break;
            case 'invert':
                for (let i = 0; i < data.length; i += 4) {
                    data[i] = 255 - data[i];
                    data[i + 1] = 255 - data[i + 1];
                    data[i + 2] = 255 - data[i + 2];
                }
                break;
        }

        this.ctx.putImageData(imageData, 0, 0);
        this._saveState();
    }

    undo() {
        if (this.historyIndex > 0) {
            this.historyIndex--;
            this._restoreState();
        }
    }

    redo() {
        if (this.historyIndex < this.history.length - 1) {
            this.historyIndex++;
            this._restoreState();
        }
    }

    _restoreState() {
        const img = new Image();
        img.onload = () => {
            this.canvas.width = img.width;
            this.canvas.height = img.height;
            this.ctx.drawImage(img, 0, 0);
        };
        img.src = this.history[this.historyIndex];
    }

    save() {
        return new Promise((resolve) => {
            this.canvas.toBlob((blob) => resolve(blob), 'image/png');
        });
    }

    getDataURL() {
        return this.canvas.toDataURL('image/png');
    }
}

window.ImageEditor = ImageEditor;
