import React, { useState } from 'react';
import { patientsApi, ApiClientError } from '../services/api';
import type { RecordUploadResponse } from '../types/api';
import {
  Upload,
  CheckCircle2,
  AlertTriangle,
  X,
  Loader2,
  FileCheck,
  AlertCircle,
  ArrowRight,
} from 'lucide-react';

interface AddRecordModalProps {
  patientId: string;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (record: RecordUploadResponse) => void;
}

export const AddRecordModal: React.FC<AddRecordModalProps> = ({
  patientId,
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [recordType, setRecordType] = useState<string>('lab_report');
  const [recordDate, setRecordDate] = useState<string>('');
  const [cycleId, setCycleId] = useState<string>('');

  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [error, setError] = useState<{ message: string; code?: string } | null>(null);
  const [result, setResult] = useState<RecordUploadResponse | null>(null);
  const [currentStep, setCurrentStep] = useState<number>(0); // 0: Form, 1: Uploading, 2: Extracting, 3: Completed / Status

  if (!isOpen) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      const validExtensions = ['.pdf', '.txt', '.json'];
      const fileExt = '.' + file.name.split('.').pop()?.toLowerCase();

      if (!validExtensions.includes(fileExt)) {
        setError({
          message: `Unsupported file type (${fileExt}). Allowed formats: .pdf, .txt, .json`,
          code: 'UNSUPPORTED_TYPE',
        });
        setSelectedFile(null);
        return;
      }

      // Max 5 MB check
      if (file.size > 5 * 1024 * 1024) {
        setError({
          message: `File size (${(file.size / (1024 * 1024)).toFixed(1)} MB) exceeds maximum allowed size (5.0 MB).`,
          code: 'PAYLOAD_TOO_LARGE',
        });
        setSelectedFile(null);
        return;
      }

      setError(null);
      setSelectedFile(file);
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setError({ message: 'Please select a file to upload.' });
      return;
    }

    setIsUploading(true);
    setError(null);
    setResult(null);
    setCurrentStep(1); // Uploaded step
    setUploadProgress(25);

    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('record_type', recordType);
    if (recordDate) {
      formData.append('record_date', recordDate);
    }
    if (cycleId.trim()) {
      formData.append('cycle_id', cycleId.trim());
    }

    try {
      setUploadProgress(60);
      setCurrentStep(2); // Extracting step

      const uploadRes = await patientsApi.uploadRecord(patientId, formData);
      setUploadProgress(100);
      setResult(uploadRes);
      setCurrentStep(3); // Completed / Validated step
      onSuccess(uploadRes);
    } catch (err: unknown) {
      setCurrentStep(0);
      if (err instanceof ApiClientError) {
        let userMessage = err.message;
        if (err.status === 409) {
          userMessage = `Exact duplicate document detected: ${err.message}`;
        } else if (err.status === 403) {
          userMessage = `Permission denied (403): Your hospital or account does not have write access for patient ${patientId}.`;
        } else if (err.status === 413) {
          userMessage = `File too large (413): The document exceeds the maximum upload size limit.`;
        } else if (err.status === 415) {
          userMessage = `Unsupported media type (415): Only .pdf, .txt, and .json documents are allowed.`;
        }
        setError({ message: userMessage, code: err.code });
      } else {
        setError({ message: 'Network failure during record upload. Please try again.' });
      }
    } finally {
      setIsUploading(false);
    }
  };

  const resetForm = () => {
    setSelectedFile(null);
    setRecordType('lab_report');
    setRecordDate('');
    setCycleId('');
    setError(null);
    setResult(null);
    setCurrentStep(0);
    setUploadProgress(0);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs animate-in fade-in duration-200">
      <div className="bg-white/95 backdrop-blur-md rounded-3xl shadow-peach-xl border border-[#FBC4AB]/50 w-full max-w-lg overflow-hidden flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-[#FBC4AB]/30 flex items-center justify-between bg-gradient-to-r from-[#FFF9F7] to-[#FFF5F2]">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-[#FFF0ED] border border-[#F8AD9D] flex items-center justify-center text-[#822828] shadow-peach-xs">
              <Upload className="w-4 h-4 text-[#F08080]" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900">Add Clinical Source Record</h2>
              <p className="text-xs text-[#822828]/70">Patient {patientId} • Ingestion Pipeline</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-[#822828] rounded-lg p-1.5 hover:bg-[#FFF0ED] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-5">
          {/* Status Stepper (Visible during or after upload) */}
          {currentStep > 0 && (
            <div className="bg-slate-50 rounded-xl p-4 border border-slate-200/80 space-y-3">
              <div className="text-xs font-semibold text-slate-700 flex items-center justify-between">
                <span>Ingestion Pipeline Progress</span>
                <span className="font-mono text-[11px] text-slate-500">
                  {result?.processing_status || (isUploading ? 'PROCESSING' : 'READY')}
                </span>
              </div>

              {/* Progress Bar */}
              <div className="w-full bg-slate-200 rounded-full h-1.5 overflow-hidden">
                <div
                  className="bg-[#F08080] h-1.5 rounded-full transition-all duration-300"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>

              {/* 3 Steps: Uploaded -> Extracting -> Validated / NEEDS_OCR */}
              <div className="grid grid-cols-3 gap-2 pt-1 text-center">
                {/* Step 1: Uploaded */}
                <div className="flex flex-col items-center">
                  <div
                    className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold mb-1 ${
                      currentStep >= 1
                        ? 'bg-emerald-100 text-emerald-700 border border-emerald-300'
                        : 'bg-slate-100 text-slate-400'
                    }`}
                  >
                    {currentStep >= 1 ? <CheckCircle2 className="w-3.5 h-3.5" /> : '1'}
                  </div>
                  <span className="text-[11px] font-medium text-slate-700">Uploaded</span>
                  <span className="text-[10px] text-slate-400">File stored & hashed</span>
                </div>

                {/* Step 2: Extracting */}
                <div className="flex flex-col items-center">
                  <div
                    className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold mb-1 ${
                      currentStep >= 2 && isUploading
                        ? 'bg-amber-100 text-amber-700 border border-amber-300 animate-pulse'
                        : currentStep >= 2
                        ? 'bg-emerald-100 text-emerald-700 border border-emerald-300'
                        : 'bg-slate-100 text-slate-400'
                    }`}
                  >
                    {currentStep >= 2 && isUploading ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : currentStep >= 2 ? (
                      <CheckCircle2 className="w-3.5 h-3.5" />
                    ) : (
                      '2'
                    )}
                  </div>
                  <span className="text-[11px] font-medium text-slate-700">Extracting</span>
                  <span className="text-[10px] text-slate-400">Text & offsets</span>
                </div>

                {/* Step 3: Validated or NEEDS_OCR */}
                <div className="flex flex-col items-center">
                  <div
                    className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold mb-1 ${
                      result?.processing_status === 'NEEDS_OCR'
                        ? 'bg-amber-100 text-amber-800 border border-amber-400'
                        : result?.processing_status === 'VALIDATED'
                        ? 'bg-emerald-100 text-emerald-700 border border-emerald-300'
                        : 'bg-slate-100 text-slate-400'
                    }`}
                  >
                    {result?.processing_status === 'NEEDS_OCR' ? (
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                    ) : result?.processing_status === 'VALIDATED' ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                    ) : (
                      '3'
                    )}
                  </div>
                  <span className="text-[11px] font-medium text-slate-700">
                    {result?.processing_status === 'NEEDS_OCR' ? 'Needs OCR' : 'Validated'}
                  </span>
                  <span className="text-[10px] text-slate-400">
                    {result?.processing_status === 'NEEDS_OCR' ? 'Scanned image' : 'Content ready'}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Error Banner */}
          {error && (
            <div className="p-3.5 bg-rose-50 border border-rose-200 rounded-xl flex items-start gap-3 text-rose-800 text-xs">
              <AlertCircle className="w-4 h-4 text-rose-500 shrink-0 mt-0.5" />
              <div className="space-y-1">
                <p className="font-semibold">{error.code ? `Error (${error.code})` : 'Upload Error'}</p>
                <p className="text-rose-700 leading-relaxed">{error.message}</p>
              </div>
            </div>
          )}

          {/* NEEDS_OCR Alert Banner */}
          {result?.processing_status === 'NEEDS_OCR' && (
            <div className="p-3.5 bg-amber-50 border border-amber-200 rounded-xl space-y-2 text-xs text-amber-900">
              <div className="flex items-center gap-2 font-bold text-amber-800">
                <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                <span>Optical Character Recognition (OCR) Required</span>
              </div>
              <p className="text-amber-700 text-[11px] leading-relaxed">
                This PDF document appears to be scanned or contains image-only pages with no embedded digital text.
                The record has been securely archived under status <span className="font-mono font-semibold">NEEDS_OCR</span>.
                OCR ingestion can be triggered when an OCR provider is configured.
              </p>
              {result.warnings.length > 0 && (
                <ul className="list-disc list-inside text-[11px] text-amber-800/80 space-y-0.5 pl-1">
                  {result.warnings.map((w, idx) => (
                    <li key={idx}>{w}</li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {/* Successful Validation Banner */}
          {result && result.processing_status === 'VALIDATED' && (
            <div className="p-3.5 bg-emerald-50 border border-emerald-200 rounded-xl space-y-2 text-xs text-emerald-900">
              <div className="flex items-center justify-between font-bold text-emerald-800">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>Document Extracted and Ingested</span>
                </div>
                <span className="font-mono text-[11px] bg-emerald-100 px-2 py-0.5 rounded text-emerald-800">
                  {result.id}
                </span>
              </div>
              <p className="text-emerald-700 text-[11px]">
                Successfully extracted {result.extracted_char_count} characters. Content text is indexed and available for clinical citations and AI synthesis.
              </p>
              {result.content_text && (
                <div className="mt-2 bg-white/80 p-2.5 rounded-lg border border-emerald-200/60 font-mono text-[10px] text-slate-700 max-h-24 overflow-y-auto whitespace-pre-wrap">
                  {result.content_text.slice(0, 300)}
                  {result.content_text.length > 300 && '...'}
                </div>
              )}
            </div>
          )}

          {/* Upload Form (Hidden if already completed successfully) */}
          {!result && (
            <form onSubmit={handleUpload} className="space-y-4">
              {/* File Dropzone */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                  Select Document (.pdf, .txt, .json) *
                </label>
                <div className="border-2 border-dashed border-slate-200 hover:border-[#F08080] rounded-xl p-5 text-center transition-colors bg-slate-50/50 hover:bg-slate-50/80 cursor-pointer relative">
                  <input
                    type="file"
                    id="record-file-input"
                    accept=".pdf,.txt,.json,application/pdf,text/plain,application/json"
                    onChange={handleFileChange}
                    disabled={isUploading}
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:cursor-not-allowed"
                  />
                  <div className="flex flex-col items-center justify-center space-y-2 pointer-events-none">
                    <div className="w-10 h-10 rounded-full bg-white shadow-2xs border border-slate-200 flex items-center justify-center text-slate-500">
                      {selectedFile ? (
                        <FileCheck className="w-5 h-5 text-emerald-600" />
                      ) : (
                        <Upload className="w-5 h-5 text-slate-400" />
                      )}
                    </div>
                    {selectedFile ? (
                      <div>
                        <p className="text-xs font-bold text-slate-800">{selectedFile.name}</p>
                        <p className="text-[11px] text-slate-500">
                          {(selectedFile.size / 1024).toFixed(1)} KB • {selectedFile.type || 'Plain text/JSON'}
                        </p>
                      </div>
                    ) : (
                      <div>
                        <p className="text-xs font-semibold text-slate-700">
                          Click to browse or drag and drop
                        </p>
                        <p className="text-[11px] text-slate-400">
                          PDF, TXT, or JSON up to 5 MB
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Record Type Selector */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                  Record Type *
                </label>
                <select
                  value={recordType}
                  onChange={(e) => setRecordType(e.target.value)}
                  disabled={isUploading}
                  className="w-full text-xs px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:border-[#F08080] text-slate-800"
                >
                  <option value="lab_report">Lab Report (Hormones, Bloodwork, Semen Analysis)</option>
                  <option value="clinical_note">Clinical Note / Doctor Consult</option>
                  <option value="imaging_report">Imaging / Ultrasound Scan Report</option>
                  <option value="embryology_report">Embryology Log / Oocyte Maturity</option>
                  <option value="operative_report">Operative / Procedure Summary</option>
                  <option value="discharge_summary">Discharge Summary</option>
                  <option value="external_record">External Hospital Document</option>
                </select>
              </div>

              {/* Grid: Optional Date & Optional Cycle ID */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                    Record Date (Optional)
                  </label>
                  <input
                    type="date"
                    value={recordDate}
                    onChange={(e) => setRecordDate(e.target.value)}
                    disabled={isUploading}
                    className="w-full text-xs px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:border-[#F08080] text-slate-800"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                    Cycle ID (Optional)
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. CYC-102-1"
                    value={cycleId}
                    onChange={(e) => setCycleId(e.target.value)}
                    disabled={isUploading}
                    className="w-full text-xs px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:border-[#F08080] text-slate-800"
                  />
                </div>
              </div>

              {/* Form Action Buttons */}
              <div className="pt-2 flex items-center justify-end gap-2.5">
                <button
                  type="button"
                  onClick={onClose}
                  disabled={isUploading}
                  className="px-4 py-2 text-xs font-semibold text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!selectedFile || isUploading}
                  className="flex items-center gap-1.5 px-4 py-2 text-xs font-bold text-white bg-gradient-to-r from-[#F08080] to-[#F4978E] hover:from-[#E07070] hover:to-[#F08080] disabled:opacity-50 disabled:cursor-not-allowed rounded-lg shadow-peach-xs transition-all"
                >
                  {isUploading ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Ingesting...</span>
                    </>
                  ) : (
                    <>
                      <Upload className="w-3.5 h-3.5" />
                      <span>Upload & Extract</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          )}

          {/* Finished Action Buttons (After successful upload) */}
          {result && (
            <div className="pt-2 flex items-center justify-between border-t border-slate-100">
              <button
                type="button"
                onClick={resetForm}
                className="text-xs font-semibold text-slate-600 hover:text-slate-900 px-3 py-1.5 rounded-lg hover:bg-[#FFF0ED] transition-colors"
              >
                Upload Another Document
              </button>
              <button
                type="button"
                onClick={onClose}
                className="flex items-center gap-1.5 px-4 py-2 text-xs font-bold text-white bg-gradient-to-r from-[#F08080] to-[#F4978E] hover:from-[#E07070] hover:to-[#F08080] rounded-lg shadow-peach-xs transition-all"
              >
                <span>Done</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
