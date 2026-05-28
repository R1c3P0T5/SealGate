# Third-Party Notices

This file records attribution and license notes for third-party models and
assets used by SealGate setup scripts or runtime components. The model binaries
listed here are downloaded locally and are not committed to this repository.

## Face Models

| Model | Upstream source | Attribution | License note |
| ----- | --------------- | ----------- | ------------ |
| YuNet face detector | [OpenCV Zoo face_detection_yunet](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet), sourced from [ShiqiYu/libfacedetection.train](https://github.com/ShiqiYu/libfacedetection.train) | Paper: "YuNet: A Tiny Millisecond-level Face Detector" by Wei Wu, Hanyang Peng, and Shiqi Yu | OpenCV Zoo lists the YuNet model directory under the MIT License. |
| SFace face recognizer | [OpenCV Zoo face_recognition_sface](https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface), from [zhongyy/SFace](https://github.com/zhongyy/SFace) | OpenCV Zoo credits Yaoyao Zhong as the SFace contributor and Chengrui Wang for ONNX conversion; paper authors are Yaoyao Zhong, Weihong Deng, Jiani Hu, Dongyue Zhao, Xian Li, and Dongchao Wen | OpenCV Zoo lists the SFace model directory under the Apache 2.0 License. |

Review the upstream model licenses before redistributing model files or
packaging them into release artifacts.
