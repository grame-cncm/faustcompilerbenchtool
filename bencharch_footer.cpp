

int main(int argc, char* argv[])
{
    long N = NBITERATIONS;
    double upper_percentile = 10.0;  // Default: keep values up to 10th percentile
    double lower_percentile = 1.0;   // Default: exclude fastest 1%

    if (argc > 4) {
        std::cerr << "Usage: " << argv[0] << " [iterations] [upper_percentile] [lower_percentile]" << std::endl;
        std::cerr << "  iterations: number of measurements (default: " << NBITERATIONS << ")" << std::endl;
        std::cerr << "  upper_percentile: upper bound of values to average (default: 10.0)" << std::endl;
        std::cerr << "  lower_percentile: lower bound to exclude outliers (default: 1.0)" << std::endl;
        std::cerr << "Example: ./reverbTank 1000 20 5  # average values from 5% to 20%" << std::endl;
        return 1;
    }

    if (argc >= 2) {
        char* endptr;
        errno    = 0;
        long val = strtol(argv[1], &endptr, 10);

        if ((errno == ERANGE && (val == LONG_MAX || val == LONG_MIN)) || (errno != 0 && val == 0)) {
            std::cerr << "Conversion error: " << argv[1] << std::endl;
            return 1;
        }

        if (endptr == argv[1]) {
            std::cerr << "No digits were found in: " << argv[1] << std::endl;
            return 1;
        }

        N = val;
    }

    if (argc >= 3) {
        char* endptr;
        errno         = 0;
        double val    = strtod(argv[2], &endptr);

        if (errno != 0 || endptr == argv[2]) {
            std::cerr << "Invalid upper percentile: " << argv[2] << std::endl;
            return 1;
        }

        if (val <= 0.0 || val > 100.0) {
            std::cerr << "Upper percentile must be between 0 and 100" << std::endl;
            return 1;
        }

        upper_percentile = val;
    }

    if (argc >= 4) {
        char* endptr;
        errno         = 0;
        double val    = strtod(argv[3], &endptr);

        if (errno != 0 || endptr == argv[3]) {
            std::cerr << "Invalid lower percentile: " << argv[3] << std::endl;
            return 1;
        }

        if (val < 0.0 || val >= 100.0) {
            std::cerr << "Lower percentile must be between 0 and 100" << std::endl;
            return 1;
        }

        lower_percentile = val;
    }

    if (lower_percentile >= upper_percentile) {
        std::cerr << "Lower percentile must be less than upper percentile" << std::endl;
        return 1;
    }

    mydsp* d = new mydsp();

    if (d == nullptr) {
        std::cerr << "Failed to create DSP object\n";
        return 1;
    }
    d->init(44100);

    // Create the input buffers
    FAUSTFLOAT* inputs[256];
    for (int i = 0; i < d->getNumInputs(); i++) {
        inputs[i] = new FAUSTFLOAT[NBSAMPLES];
        for (int j = 0; j < NBSAMPLES; j++) {
            inputs[i][j] = 0.0;
        }
        inputs[i][0] = 1.0;
    }

    // Create the output buffers
    FAUSTFLOAT* outputs[256];
    for (int i = 0; i < d->getNumOutputs(); i++) {
        outputs[i] = new FAUSTFLOAT[NBSAMPLES];
        for (int j = 0; j < NBSAMPLES; j++) {
            outputs[i][j] = 0.0;
        }
    }

    // Extended warmup to ensure stable CPU state
    for (int i = 0; i < 50; i++) {
        d->compute(NBSAMPLES, inputs, outputs);
    }

    // Collect N measurements
    std::vector<double> measurements;
    measurements.reserve(N);

    for (long i = 0; i < N; i++) {
        auto start = std::chrono::high_resolution_clock::now();
        d->compute(NBSAMPLES, inputs, outputs);
        auto end = std::chrono::high_resolution_clock::now();
        std::chrono::duration<double> duration = end - start;
        measurements.push_back(duration.count());
    }

    // Sort measurements
    std::sort(measurements.begin(), measurements.end());

    // Compute indices for the percentile range
    size_t lower_index = static_cast<size_t>((measurements.size() * lower_percentile) / 100.0);
    size_t upper_index = static_cast<size_t>((measurements.size() * upper_percentile) / 100.0);

    // Ensure valid range
    if (upper_index >= measurements.size()) upper_index = measurements.size() - 1;
    if (lower_index >= upper_index) lower_index = upper_index > 0 ? upper_index - 1 : 0;

    size_t sample_size = upper_index - lower_index;
    if (sample_size < 1) sample_size = 1;

    // Compute mean of values in the percentile range
    double sum = 0.0;
    for (size_t i = lower_index; i < upper_index; i++) {
        sum += measurements[i];
    }
    double result = sum / sample_size;

    // Print the result in milliseconds
    std::cout << argv[0] << " " << result * 1000 << " ms" << std::endl;

    // Cleanup
    for (int i = 0; i < d->getNumInputs(); i++) {
        delete[] inputs[i];
    }
    for (int i = 0; i < d->getNumOutputs(); i++) {
        delete[] outputs[i];
    }
    delete d;

    return 0;
}
