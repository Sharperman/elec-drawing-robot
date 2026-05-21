/**
 * 文件上传组件 - 拖拽上传图片，预览缩略图
 */
import React, { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, X, ImageIcon } from 'lucide-react';
import { clsx } from 'clsx';

interface FileUploadProps {
  onFileSelected: (file: File) => void;
  onClear: () => void;
  previewUrl?: string | null;
  isUploading?: boolean;
  className?: string;
}

const FileUpload: React.FC<FileUploadProps> = ({
  onFileSelected,
  onClear,
  previewUrl,
  isUploading = false,
  className,
}) => {
  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      if (acceptedFiles.length > 0) {
        onFileSelected(acceptedFiles[0]);
      }
    },
    [onFileSelected]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'image/jpeg': ['.jpg', '.jpeg'],
      'image/png': ['.png'],
      'image/bmp': ['.bmp'],
      'image/tiff': ['.tiff', '.tif'],
      'image/webp': ['.webp'],
    },
    maxFiles: 1,
    maxSize: 10 * 1024 * 1024, // 10MB
    disabled: isUploading,
  });

  if (previewUrl) {
    return (
      <div className={clsx('relative inline-block', className)}>
        <img
          src={previewUrl}
          alt="上传的图片"
          className="max-h-24 max-w-48 rounded-lg object-contain border border-gray-600"
        />
        <button
          onClick={onClear}
          className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-gray-700 
                     border border-gray-500 flex items-center justify-center
                     hover:bg-red-600 transition-colors"
        >
          <X className="w-3 h-3 text-white" />
        </button>
        {isUploading && (
          <div className="absolute inset-0 rounded-lg bg-black/50 flex items-center justify-center">
            <div className="w-5 h-5 border-2 border-gray-600 border-t-blue-400 rounded-full animate-spin" />
          </div>
        )}
      </div>
    );
  }

  return (
    <div
      {...getRootProps()}
      className={clsx(
        'border-2 border-dashed rounded-lg p-3 cursor-pointer transition-colors text-center',
        isDragActive
          ? 'border-blue-400 bg-blue-900/20'
          : 'border-gray-600 hover:border-gray-500 hover:bg-gray-800/50',
        className
      )}
    >
      <input {...getInputProps()} />
      <div className="flex flex-col items-center gap-1">
        {isDragActive ? (
          <Upload className="w-5 h-5 text-blue-400" />
        ) : (
          <ImageIcon className="w-5 h-5 text-gray-500" />
        )}
        <p className="text-xs text-gray-500">
          {isDragActive ? '释放以上传' : '拖拽或点击上传图片'}
        </p>
        <p className="text-xs text-gray-600">JPG/PNG/BMP，最大 10MB</p>
      </div>
    </div>
  );
};

export default FileUpload;
