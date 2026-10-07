# Warehouse trained weights

No trained model is supplied. Place your trusted warehouse detection model at
models/best.pt before building Dockerfile.yolo, or configure the verified HTTPS
download described in defense/DEPLOYMENT.md. The ordinary Dockerfile remains demo.

Set MOVIS_MODE=yolo and MOVIS_WEIGHTS=/app/models/best.pt for an embedded file.
The Docker ignore rules permit only this weights file; Git still ignores .pt
by default to avoid accidentally publishing a private model. Use a private repo
or controlled download when the weights must remain private.
