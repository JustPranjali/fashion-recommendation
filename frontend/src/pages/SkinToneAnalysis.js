import React, { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const SkinToneAnalysis = () => {
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const fileInputRef = useRef(null);
  const navigate = useNavigate();

  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      if (!file.type.startsWith('image/')) {
        setError('Please select a valid image file');
        return;
      }
      
      setSelectedFile(file);
      setError('');
      
      // Create preview URL
      const reader = new FileReader();
      reader.onload = (e) => setPreviewUrl(e.target.result);
      reader.readAsDataURL(file);
    }
  };

  const handleAnalyze = async () => {
    if (!selectedFile) {
      setError('Please select an image first');
      return;
    }

    setLoading(true);
    setError('');

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      const token = localStorage.getItem('token');
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      
      const response = await axios.post(`${API}/analyze-skin-tone`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
          ...headers
        }
      });

      setResult(response.data);
    } catch (error) {
      console.error('Analysis error:', error);
      setError(error.response?.data?.detail || 'Analysis failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleGetRecommendations = () => {
    if (result) {
      navigate('/recommendations', {
        state: {
          skinTone: result.detected_skin_tone,
          recommendedColors: result.recommended_colors
        }
      });
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 py-12">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">
            Skin Tone Analysis
          </h1>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto">
            Upload your photo to discover your skin tone and get personalized color recommendations
          </p>
        </div>

        <div className="bg-white rounded-lg shadow-lg p-8">
          {!result ? (
            <div className="space-y-8">
              {/* File Upload Section */}
              <div className="text-center">
                <div
                  className="border-2 border-dashed border-gray-300 rounded-lg p-12 hover:border-purple-400 transition-colors cursor-pointer"
                  onClick={() => fileInputRef.current?.click()}
                >
                  {previewUrl ? (
                    <div className="space-y-4">
                      <img
                        src={previewUrl}
                        alt="Preview"
                        className="mx-auto h-64 w-64 object-cover rounded-lg"
                      />
                      <p className="text-sm text-gray-600">Click to change image</p>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      <svg
                        className="mx-auto h-16 w-16 text-gray-400"
                        stroke="currentColor"
                        fill="none"
                        viewBox="0 0 48 48"
                      >
                        <path
                          d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02"
                          strokeWidth={2}
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
                      <div>
                        <p className="text-lg font-medium text-gray-900">
                          Upload your photo
                        </p>
                        <p className="text-sm text-gray-600">
                          PNG, JPG, GIF up to 10MB
                        </p>
                      </div>
                    </div>
                  )}
                </div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={handleFileSelect}
                  className="hidden"
                />
              </div>

              {/* Instructions */}
              <div className="bg-purple-50 rounded-lg p-6">
                <h3 className="text-lg font-medium text-purple-900 mb-2">
                  For best results:
                </h3>
                <ul className="space-y-1 text-purple-800">
                  <li>• Use good lighting (natural light is best)</li>
                  <li>• Face the camera directly</li>
                  <li>• Remove makeup if possible</li>
                  <li>• Ensure your face is clearly visible</li>
                </ul>
              </div>

              {error && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                  <p className="text-red-800">{error}</p>
                </div>
              )}

              {/* Analyze Button */}
              <div className="text-center">
                <button
                  onClick={handleAnalyze}
                  disabled={loading || !selectedFile}
                  className="bg-purple-600 text-white px-8 py-3 rounded-lg font-medium hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {loading ? (
                    <div className="flex items-center">
                      <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      Analyzing...
                    </div>
                  ) : (
                    'Analyze Skin Tone'
                  )}
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-8">
              {/* Results Section */}
              <div className="text-center">
                <h2 className="text-2xl font-bold text-gray-900 mb-4">
                  Analysis Complete!
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                  <div>
                    <img
                      src={previewUrl}
                      alt="Analyzed"
                      className="mx-auto h-64 w-64 object-cover rounded-lg"
                    />
                  </div>
                  <div className="space-y-6">
                    <div>
                      <h3 className="text-lg font-medium text-gray-900 mb-2">
                        Your Skin Tone
                      </h3>
                      <div className="flex items-center justify-center space-x-3">
                        <div
                          className="w-12 h-12 rounded-full border-2 border-gray-300"
                          style={{ backgroundColor: result.detected_skin_tone }}
                        ></div>
                        <span className="text-lg font-mono">
                          {result.detected_skin_tone}
                        </span>
                      </div>
                    </div>
                    
                    <div>
                      <h3 className="text-lg font-medium text-gray-900 mb-2">
                        Recommended Colors
                      </h3>
                      <div className="flex flex-wrap gap-2 justify-center">
                        {result.recommended_colors.map((color, index) => (
                          <span
                            key={index}
                            className="bg-purple-100 text-purple-800 px-3 py-1 rounded-full text-sm font-medium"
                          >
                            {color}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <button
                  onClick={handleGetRecommendations}
                  className="bg-purple-600 text-white px-8 py-3 rounded-lg font-medium hover:bg-purple-700 transition-colors"
                >
                  Get Outfit Recommendations
                </button>
                <button
                  onClick={() => {
                    setResult(null);
                    setPreviewUrl('');
                    setSelectedFile(null);
                  }}
                  className="bg-gray-300 text-gray-700 px-8 py-3 rounded-lg font-medium hover:bg-gray-400 transition-colors"
                >
                  Analyze Another Photo
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default SkinToneAnalysis;