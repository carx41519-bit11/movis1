"""Explicit training entry point; requires real labeled data and ultralytics."""
import argparse
from pathlib import Path

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--data',required=True)
    parser.add_argument('--base',required=True,help='Pretrained YOLO detection weights, e.g. yolo26n.pt')
    parser.add_argument('--epochs',type=int,default=50)
    parser.add_argument('--imgsz',type=int,default=640)
    parser.add_argument('--device',default='cpu')
    args=parser.parse_args()
    config=Path(args.data)
    if not config.is_file() or 'REPLACE' in config.read_text():
        parser.error('Provide a real dataset YAML with actual class names')
    from ultralytics import YOLO
    model=YOLO(args.base)
    model.train(data=str(config.resolve()),epochs=args.epochs,imgsz=args.imgsz,device=args.device,project='runs',name='movis',seed=42)
    print('Training run finished. Validate best.pt on the held-out test set before deployment.')

if __name__=='__main__':main()
