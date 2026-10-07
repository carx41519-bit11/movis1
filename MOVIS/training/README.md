# Train rice detection when your dataset is ready

No dataset, trained rice weights or measured accuracy are included. Demo scanning produces synthetic labels and boxes and must not be used to measure model performance.

Collect new rear-camera images at 1x from Elder Jay with the owner's permission. Include Sinandomeng, Jasmine rice and Buko Pandan rice in 25 kg sacks, mixed products, varied lighting, occlusion, stacks, empty scenes and confusing backgrounds. Annotate each visible sack in CVAT and export YOLO labels. Keep hidden physical stock outside visible-detection ground truth.

Use labels `sinandomeng`, `jasmine`, `buko_pandan` in both dataset.yaml and administrator product settings. One sack is one unit; scanning does not measure weight or inspect the rice inside.

Group related images by capture session before splitting about 70% training, 15% validation and 15% final test. Keep augmentation in training. Do not tune settings using final-test images.

Copy dataset.yaml.example to dataset.yaml and set the real dataset path. Use images/train, images/val and images/test with matching labels directories. Install Ultralytics in a separate training environment, then run:

```powershell
python train.py --data dataset.yaml --base yolo26n.pt --epochs 50 --device cpu
yolo detect val model=runs/movis/weights/best.pt data=dataset.yaml split=test
```

These are starting commands, not an accuracy claim. Record the selected weights SHA256, software version, confidence threshold (backend: 0.35), precision, recall and mAP. Also record uncorrected predicted visible counts, ground-truth visible counts, image conditions and phone/server processing times. User-corrected quantities are not raw model measurements.

For count MAE and exact-count rate, evaluate_counts.py accepts a JSON array containing product, condition, actual, predicted and user_corrected:false. Example record shape only: {"product":"sinandomeng","condition":"bright","actual":4,"predicted":3,"user_corrected":false}. Run `python evaluate_counts.py --records measured-counts.json --output count-metrics.json`. Use held-out YOLO validation for precision, recall and mAP.

Copy your selected trusted best.pt to models/best.pt. Set MOVIS_MODE=yolo and MOVIS_WEIGHTS to that path, or use the existing checksum-verified HTTPS loader. Match model labels exactly. Missing real weights fail startup in yolo mode. Test the hosted server and POCO F5 Pro camera with real warehouse sacks before collecting research results.

Official references: [YOLO26](https://docs.ultralytics.com/models/yolo26/), [training](https://docs.ultralytics.com/modes/train/), [validation](https://docs.ultralytics.com/modes/val/).
