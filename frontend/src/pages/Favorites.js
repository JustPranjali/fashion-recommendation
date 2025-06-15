import React, { useState, useEffect, useContext } from 'react';
import axios from 'axios';
import { AuthContext } from '../App';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const Favorites = () => {
  const [favorites, setFavorites] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const { user } = useContext(AuthContext);

  useEffect(() => {
    fetchFavorites();
  }, []);

  const fetchFavorites = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await axios.get(`${API}/favorites`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      setFavorites(response.data.favorites || []);
    } catch (error) {
      console.error('Error fetching favorites:', error);
      setError('Failed to load favorites');
    } finally {
      setLoading(false);
    }
  };

  const removeFavorite = async (itemId) => {
    try {
      const token = localStorage.getItem('token');
      await axios.delete(`${API}/favorites/${itemId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      setFavorites(favorites.filter(fav => fav.item_id !== itemId));
    } catch (error) {
      console.error('Error removing favorite:', error);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 py-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center">
            <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-purple-600 mx-auto"></div>
            <p className="mt-4 text-gray-600">Loading your favorites...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-12">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">
            My Favorites
          </h1>
          <p className="text-xl text-gray-600">
            Your saved fashion recommendations
          </p>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-6 mb-8">
            <p className="text-red-800">{error}</p>
            <button
              onClick={fetchFavorites}
              className="mt-2 bg-red-600 text-white px-4 py-2 rounded-lg hover:bg-red-700 transition-colors"
            >
              Try Again
            </button>
          </div>
        )}

        {favorites.length === 0 ? (
          <div className="text-center py-12">
            <div className="text-6xl mb-4">💝</div>
            <h3 className="text-2xl font-bold text-gray-900 mb-4">
              No favorites yet
            </h3>
            <p className="text-gray-600 mb-6">
              Start exploring outfit recommendations and save the ones you love!
            </p>
            <a
              href="/analyze"
              className="bg-purple-600 text-white px-8 py-3 rounded-lg font-medium hover:bg-purple-700 transition-colors inline-block"
            >
              Discover Outfits
            </a>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            {favorites.map((favorite) => (
              <div key={favorite.id} className="bg-white rounded-lg shadow-lg overflow-hidden hover:shadow-xl transition-shadow">
                <div className="relative">
                  {/* Placeholder image */}
                  <div className="h-64 bg-gradient-to-br from-purple-100 to-pink-100 flex items-center justify-center">
                    <div className="text-center">
                      <div className="text-4xl mb-2">👔</div>
                      <p className="text-sm text-gray-600">Product Image</p>
                    </div>
                  </div>
                  
                  {/* Remove Favorite Button */}
                  <button
                    onClick={() => removeFavorite(favorite.item_id)}
                    className="absolute top-4 right-4 p-2 rounded-full bg-red-500 text-white hover:bg-red-600 transition-colors"
                  >
                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                    </svg>
                  </button>
                </div>
                
                <div className="p-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-2 line-clamp-2">
                    {favorite.product_name}
                  </h3>
                  
                  <div className="flex items-center text-sm text-gray-600 mb-4">
                    <span className="font-medium mr-2">Color:</span>
                    <span className="bg-purple-100 text-purple-800 px-2 py-1 rounded-full text-xs">
                      {favorite.base_colour}
                    </span>
                  </div>
                  
                  <div className="text-xs text-gray-500">
                    Added {new Date(favorite.created_at).toLocaleDateString()}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default Favorites;