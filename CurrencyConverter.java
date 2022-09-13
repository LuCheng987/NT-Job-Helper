package com.example.ass1;
import java.io.*;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;
import java.util.Scanner;

public class CurrencyConverter {
    //Conversion rates, average, median, maximum, minimum, standard deviation
    public static double convertRate(double currency, double exchangeRate) {
        return currency * exchangeRate;
    }

    public static double extractRate(String fileName, String conRow, String conCol) {
        try {
            File table = new File(fileName);
            Scanner reader = new Scanner(table);

            String currency = reader.nextLine();
            String[] currencyList = currency.split(",", 0);
            int row = 0;
            double answer = 0;

            for (int i = 0; i < currencyList.length; i++) {
                if (currencyList[i].equals(conRow)){
                    row = i;
                    break;
                }
            }

            while (reader.hasNextLine()) {
                currency = reader.nextLine();
                currencyList = currency.split(",", 0);
                if (currencyList[0].equals(conCol)) {
                    answer = Double.parseDouble(currencyList[row]);
                    break;
                }
            }
            reader.close();

            return answer;
        } catch (FileNotFoundException e) {
            System.out.println("Error: file not found.");
        }
        return -1;
    }

    public static List<Double> exchangeRateList(int startDate, int endDate, String rowName, String colName) throws IOException{
        File dir = new File("list of tables"); //list of tables is the folder that contains all the tables
        File[] files = dir.listFiles();
        List<Double> exchangeList = new ArrayList<>();

        for (File file: files) {
            if (file.isFile()) {
                BufferedReader inputStream = null;
                String line;
                try {
                    inputStream = new BufferedReader(new FileReader(file));
                    while ((line = inputStream.readLine()) != null) {
                        double rate = extractRate(line, rowName, colName); //only add rate if it adheres to the dates.
                        exchangeList.add(rate);
                    }
                } catch (IOException e) {
                    System.out.println("File cannot be opened");
                } finally {
                    if (inputStream != null) {
                        inputStream.close();
                    }
                }
            }
        }
        return exchangeList;
    }

    public static double average(List<Double> array) {
        double sum = 0;
        for (int i = 0; i < array.size(); i++) {
            sum += array.get(i);
        }
        return sum/array.size();
    }
    public static double median(List<Double> array) {
        return array.get(array.size()/2);
    }
    public static double maximum(List<Double> array) {
        double max = array.get(0);
        for (int i = 0; i < array.size(); i++) {
            if (array.get(i) > max) {
                max = array.get(i);
            }
        }
        return max;
    }
    public static double minimum(List<Double> array) {
        double min = array.get(0);
        for (int i = 0; i < array.size(); i++) {
            if (array.get(i) < min) {
                min = array.get(i);
            }
        }
        return min;
    }
    public static double standardDeviation(List<Double> array) {
        double sd = 0;
        double mean = average(array);
        for (int i = 0; i < array.size(); i++) {
            sd += Math.pow(array.get(i) - mean, 2);
        }
        return Math.sqrt(sd/array.size());
    }

    //This is step 9. It prints the conversion rates, average, median, maximum, minimum, standard deviation over two dates
    public static void printSummary(List<Double> array) {
        System.out.println("Conversion Rates: " + array);
        System.out.format("Average: %.2f\n", average(array));
        System.out.format("Median: %.2f\n", median(array));
        System.out.format("Maximum: %.2f\n", maximum(array));
        System.out.format("Minimum: %.2f\n", minimum(array));
        System.out.format("Standard Deviation: %.2f\n", standardDeviation(array));
    }

    public static void main(String[] args) {
        convertRate(1, 2);
        List<Double> list = new ArrayList<>();
        list.add(1.0);
        list.add(2.0);
        list.add(3.0);
        list.add(4.0);
        list.add(5.0);

        printSummary(list);
    }
}
