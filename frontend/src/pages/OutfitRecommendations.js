import React, { useState, useEffect, useContext } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { AuthContext } from '../App';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const OutfitRecommendations = () => {
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [gender, setGender] = useState('Men');
  const [favorites, setFavorites] = useState(new Set());
  const location = useLocation();
  const navigate = useNavigate();
  const { user } = useContext(AuthContext);

  const skinToneData = location.state;

  useEffect(() => {
    if (skinToneData) {
      fetchRecommendations();
    }
    if (user) {
      fetchFavorites();
    }
  }, [skinToneData, gender, user]);

  const fetchRecommendations = async () => {
    setLoading(true);
    setError('');

    try {
      const colors = skinToneData?.recommendedColors?.join(',') || 'Black,White,Blue';
      const response = await axios.get(`${API}/outfit-recommendations`, {
        params: {
          gender: gender,
          recommended_colors: colors,
          limit: 5
        }
      });

      setRecommendations(response.data.recommendations || []);
    } catch (error) {
      console.error('Recommendations error:', error);
      setError('Failed to fetch recommendations. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const fetchFavorites = async () => {
    if (!user) return;

    try {
      const token = localStorage.getItem('token');
      const response = await axios.get(`${API}/favorites`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      const favoriteIds = new Set(response.data.favorites.map(fav => fav.item_id));
      setFavorites(favoriteIds);
    } catch (error) {
      console.error('Error fetching favorites:', error);
    }
  };

  const toggleFavorite = async (item) => {
    if (!user) {
      navigate('/login');
      return;
    }

    const token = localStorage.getItem('token');
    const isCurrentlyFavorite = favorites.has(item.item_id);

    try {
      if (isCurrentlyFavorite) {
        await axios.delete(`${API}/favorites/${item.item_id}`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setFavorites(prev => {
          const newSet = new Set(prev);
          newSet.delete(item.item_id);
          return newSet;
        });
      } else {
        await axios.post(`${API}/favorites`, {
          item_id: item.item_id,
          product_name: item.product_name,
          base_colour: item.base_colour
        }, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setFavorites(prev => new Set([...prev, item.item_id]));
      }
    } catch (error) {
      console.error('Error toggling favorite:', error);
    }
  };

  const handleAnalyzeNew = () => {
    navigate('/analyze');
  };

  return (
    <div className="min-h-screen bg-gray-50 py-12">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">
            Outfit Recommendations
          </h1>
          {skinToneData && (
            <div className="mb-6">
              <p className="text-xl text-gray-600 mb-2">
                Based on your skin tone analysis
              </p>
              <div className="flex items-center justify-center space-x-4">
                <div
                  className="w-8 h-8 rounded-full border-2 border-gray-300"
                  style={{ backgroundColor: skinToneData.skinTone }}
                ></div>
                <div className="flex flex-wrap gap-2">
                  {skinToneData.recommendedColors?.map((color, index) => (
                    <span
                      key={index}
                      className="bg-purple-100 text-purple-800 px-2 py-1 rounded-full text-sm"
                    >
                      {color}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Gender Selection */}
        <div className="bg-white rounded-lg shadow p-6 mb-8">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Select Gender</h3>
          <div className="flex space-x-4">
            {['Men', 'Women'].map((g) => (
              <button
                key={g}
                onClick={() => setGender(g)}
                className={`px-6 py-2 rounded-lg font-medium transition-colors ${
                  gender === g
                    ? 'bg-purple-600 text-white'
                    : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                }`}
              >
                {g}
              </button>
            ))}
          </div>
        </div>

        {/* Loading State */}
        {loading && (
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-purple-600 mx-auto"></div>
            <p className="mt-4 text-gray-600">Finding perfect outfits for you...</p>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-6 mb-8">
            <p className="text-red-800">{error}</p>
            <button
              onClick={fetchRecommendations}
              className="mt-2 bg-red-600 text-white px-4 py-2 rounded-lg hover:bg-red-700 transition-colors"
            >
              Try Again
            </button>
          </div>
        )}

        {/* Recommendations Grid */}
        {!loading && recommendations.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 mb-12">
            {recommendations.map((item, index) => (
              <div key={item.item_id} className="bg-white rounded-lg shadow-lg overflow-hidden hover:shadow-xl transition-shadow">
                <div className="relative">
                  {/* Placeholder image - in real app would use actual product images */}
                  <div className="h-64 bg-gradient-to-br from-purple-100 to-pink-100 flex items-center justify-center">
                    <div className="text-center">
                      <div className="text-4xl mb-2">👔</div>
                      <p className="text-sm text-gray-600">Product Image</p>
                    </div>
                  </div>
                  
                  {/* Favorite Button */}
                  <button
                    onClick={() => toggleFavorite(item)}
                    className={`absolute top-4 right-4 p-2 rounded-full transition-colors ${
                      favorites.has(item.item_id)
                        ? 'bg-red-500 text-white'
                        : 'bg-white text-gray-400 hover:text-red-500'
                    }`}
                  >
                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z" clipRule="evenodd" />
                    </svg>
                  </button>
                </div>
                
                <div className="p-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-2 line-clamp-2">
                    {item.product_name}
                  </h3>
                  
                  <div className="space-y-2">
                    <div className="flex items-center text-sm text-gray-600">
                      <span className="font-medium mr-2">Category:</span>
                      <span>{item.category} - {item.sub_category}</span>
                    </div>
                    
                    <div className="flex items-center text-sm text-gray-600">
                      <span className="font-medium mr-2">Type:</span>
                      <span>{item.article_type}</span>
                    </div>
                    
                    <div className="flex items-center text-sm text-gray-600">
                      <span className="font-medium mr-2">Color:</span>
                      <span className="bg-purple-100 text-purple-800 px-2 py-1 rounded-full text-xs">
                        {item.base_colour}
                      </span>
                    </div>
                    
                    <div className="flex items-center text-sm text-gray-600">
                      <span className="font-medium mr-2">Season:</span>
                      <span>{item.season}</span>
                    </div>
                    
                    <div className="flex items-center text-sm text-gray-600">
                      <span className="font-medium mr-2">Usage:</span>
                      <span>{item.usage}</span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* No Recommendations */}
        {!loading && recommendations.length === 0 && (
          <div className="text-center py-12">
            <div className="text-6xl mb-4">🛍️</div>
            <h3 className="text-2xl font-bold text-gray-900 mb-4">
              No recommendations found
            </h3>
            <p className="text-gray-600 mb-6">
              Try analyzing your skin tone first or adjust your preferences.
            </p>
            <button
              onClick={handleAnalyzeNew}
              className="bg-purple-600 text-white px-8 py-3 rounded-lg font-medium hover:bg-purple-700 transition-colors"
            >
              Analyze Skin Tone
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default OutfitRecommendations;